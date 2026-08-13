"""BankSource interface and CSV/OFX implementation."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.ledger.service import normalize_payee
from app.money import money


@dataclass
class BankRow:
    tx_date: date
    amount: Decimal  # signed: negative = money out of bank
    payee: str
    narration: str = ""
    raw: dict[str, Any] | None = None

    @property
    def fingerprint(self) -> str:
        return f"{self.tx_date.isoformat()}|{money(abs(self.amount))}|{normalize_payee(self.payee)}"


class BankSource(ABC):
    @abstractmethod
    def extract(self, content: bytes, filename: str) -> list[BankRow]:
        ...


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y%m%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    # OFX style YYYYMMDDHHMMSS
    if re.match(r"^\d{8}", value):
        return datetime.strptime(value[:8], "%Y%m%d").date()
    raise ValueError(f"Unrecognized date: {value}")


def _parse_amount(value: str) -> Decimal:
    v = value.strip().replace(",", "").replace("$", "")
    if v.startswith("(") and v.endswith(")"):
        v = "-" + v[1:-1]
    return money(v)


class CsvOfxSource(BankSource):
    """Parse CSV or OFX/QFX bank exports into normalized BankRow list."""

    def extract(self, content: bytes, filename: str) -> list[BankRow]:
        name = filename.lower()
        text = content.decode("utf-8", errors="replace")
        if name.endswith((".ofx", ".qfx")) or text.lstrip().startswith(("<OFX", "OFXHEADER")):
            return self._parse_ofx(text)
        return self._parse_csv(text)

    def _parse_csv(self, text: str) -> list[BankRow]:
        # sniff delimiter
        sample = text[:2048]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames:
            return []

        fields = {f.lower().strip(): f for f in reader.fieldnames if f}
        date_key = self._pick(fields, ["date", "transaction date", "posted date", "trans date"])
        amount_key = self._pick(fields, ["amount", "transaction amount", "amt"])
        debit_key = self._pick(fields, ["debit", "withdrawal", "outflow"])
        credit_key = self._pick(fields, ["credit", "deposit", "inflow"])
        payee_key = self._pick(
            fields,
            ["payee", "description", "merchant", "name", "memo", "narrative"],
        )
        memo_key = self._pick(fields, ["memo", "narration", "notes", "details"])

        rows: list[BankRow] = []
        for raw in reader:
            if not any((raw.get(v) or "").strip() for v in raw):
                continue
            d = _parse_date(str(raw[date_key]))
            if amount_key:
                amt = _parse_amount(str(raw[amount_key]))
            else:
                debit = _parse_amount(str(raw.get(debit_key) or "0")) if debit_key else money(0)
                credit = _parse_amount(str(raw.get(credit_key) or "0")) if credit_key else money(0)
                # debit leaves the account (negative), credit enters (positive)
                amt = money(credit - abs(debit)) if debit_key or credit_key else money(0)
            payee = str(raw.get(payee_key) or "").strip() if payee_key else ""
            narr = str(raw.get(memo_key) or "").strip() if memo_key else ""
            if not payee:
                payee = narr or "Unknown"
            rows.append(BankRow(tx_date=d, amount=amt, payee=payee, narration=narr, raw=dict(raw)))
        return rows

    def _pick(self, fields: dict[str, str], candidates: list[str]) -> str | None:
        for c in candidates:
            if c in fields:
                return fields[c]
        return None

    def _parse_ofx(self, text: str) -> list[BankRow]:
        # Minimal OFX SGML parser for STMTTRN blocks
        rows: list[BankRow] = []
        # normalize tags
        blocks = re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, flags=re.IGNORECASE | re.DOTALL)
        if not blocks:
            # some QFX omit closing tags — split on STMTTRN
            parts = re.split(r"<STMTTRN>", text, flags=re.IGNORECASE)
            blocks = parts[1:]

        for block in blocks:
            def tag(name: str) -> str | None:
                m = re.search(rf"<{name}>([^<\r\n]+)", block, flags=re.IGNORECASE)
                return m.group(1).strip() if m else None

            dt_raw = tag("DTPOSTED") or tag("DTUSER")
            amt_raw = tag("TRNAMT")
            if not dt_raw or amt_raw is None:
                continue
            payee = tag("NAME") or tag("PAYEE") or tag("MEMO") or "Unknown"
            memo = tag("MEMO") or ""
            rows.append(
                BankRow(
                    tx_date=_parse_date(dt_raw),
                    amount=_parse_amount(amt_raw),
                    payee=payee,
                    narration=memo,
                )
            )
        return rows


def content_fingerprint(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]
