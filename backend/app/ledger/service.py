"""Append-only beancount text emitter and reader."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from beancount import loader
from beancount.core import data, getters, realization
from beancount.core.number import D
from filelock import FileLock
from openpyxl import Workbook

from app.money import assert_no_float, money


class LedgerError(Exception):
    """Structured ledger failure."""

    def __init__(self, message: str, errors: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


@dataclass
class LedgerLoadResult:
    entries: list[Any]
    options: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    path: str = ""

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def _format_error(err: Any, path: str) -> dict[str, Any]:
    source = getattr(err, "source", None)
    line = None
    file = path
    if source:
        file = getattr(source, "filename", path) or path
        line = getattr(source, "lineno", None)
    return {
        "file": str(file),
        "line": line,
        "message": str(err),
    }


def load_ledger(path: str | Path) -> LedgerLoadResult:
    path = Path(path)
    if not path.exists():
        raise LedgerError(f"Ledger file not found: {path}")
    entries, errors, options = loader.load_file(str(path))
    structured = [_format_error(e, str(path)) for e in errors]
    return LedgerLoadResult(entries=list(entries), options=options, errors=structured, path=str(path))


def _lock_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".lock")


def _format_amount(amount: Decimal) -> str:
    assert_no_float(amount)
    q = money(amount)
    return f"{q} USD"


def _escape_meta(value: str) -> str:
    return value.replace('"', '\\"')


def format_open(account: str, open_date: date | None = None) -> str:
    d = open_date or date.today()
    return f"{d.isoformat()} open {account}\n"


def format_transaction(
    tx_date: date,
    payee: str | None,
    narration: str | None,
    postings: list[dict[str, Any]],
    meta: dict[str, Any] | None = None,
    flag: str = "*",
) -> str:
    """
    Emit a balanced double-entry transaction as beancount text.
    postings: [{account, amount: Decimal|str|None, currency?}]
    One posting may omit amount (auto-balance) but we require explicit amounts
    and validate balance ourselves.
    """
    lines: list[str] = []
    if meta:
        for k, v in meta.items():
            if k.startswith("_"):
                continue
            lines.append(f'  {k}: "{_escape_meta(str(v))}"')

    header_payee = f' "{payee}"' if payee else ""
    header_narr = f' "{narration or ""}"'
    lines.insert(0, f"{tx_date.isoformat()} {flag}{header_payee}{header_narr}")

    total = Decimal("0")
    for p in postings:
        account = p["account"]
        amt = p.get("amount")
        tags = []
        if p.get("class"):
            tags.append(f'class: "{_escape_meta(str(p["class"]))}"')
        if p.get("location"):
            tags.append(f'location: "{_escape_meta(str(p["location"]))}"')
        if amt is None:
            raise LedgerError("All posting amounts must be explicit")
        assert_no_float(amt)
        amt_d = money(amt)
        total += amt_d
        line = f"  {account}  {_format_amount(amt_d)}"
        lines.append(line)
        for t in tags:
            # beancount posting metadata sits under the posting
            lines.append(f"    {t}")

    if money(total) != Decimal("0.00"):
        raise LedgerError(f"Unbalanced transaction: sum={total}")

    return "\n".join(lines) + "\n\n"


def _check_writable(path: Path, close_date: str | None, entry_date: date) -> None:
    if close_date:
        locked = date.fromisoformat(close_date)
        if entry_date <= locked:
            raise LedgerError(
                f"Period locked through {close_date}; cannot append entry dated {entry_date.isoformat()}"
            )


def append_text(path: str | Path, text: str) -> None:
    path = Path(path)
    lock = FileLock(str(_lock_path(path)))
    with lock:
        with path.open("a", encoding="utf-8") as f:
            if not text.startswith("\n") and path.stat().st_size > 0:
                f.write("\n")
            f.write(text)


def append_transaction(
    path: str | Path,
    tx_date: date,
    postings: list[dict[str, Any]],
    payee: str | None = None,
    narration: str | None = None,
    meta: dict[str, Any] | None = None,
    close_date: str | None = None,
) -> LedgerLoadResult:
    path = Path(path)
    result = load_ledger(path)
    if not result.ok:
        raise LedgerError("Ledger has errors; writes blocked until fixed", result.errors)

    _check_writable(path, close_date, tx_date)
    text = format_transaction(tx_date, payee, narration, postings, meta=meta)
    append_text(path, text)

    after = load_ledger(path)
    if not after.ok:
        raise LedgerError("Append produced ledger errors", after.errors)
    return after


def add_account(
    path: str | Path,
    account: str,
    open_date: date | None = None,
) -> LedgerLoadResult:
    path = Path(path)
    result = load_ledger(path)
    if not result.ok:
        raise LedgerError("Ledger has errors; writes blocked until fixed", result.errors)

    existing = getters.get_accounts(result.entries)
    if account in existing:
        return result

    text = format_open(account, open_date)
    append_text(path, f"\n; auto-opened account\n{text}")
    after = load_ledger(path)
    if not after.ok:
        raise LedgerError("Opening account produced ledger errors", after.errors)
    return after


def get_accounts(path: str | Path) -> list[dict[str, Any]]:
    result = load_ledger(path)
    if not result.ok:
        raise LedgerError("Ledger has errors", result.errors)
    accounts = sorted(getters.get_accounts(result.entries))
    # leaf vs parent
    account_set = set(accounts)
    out = []
    for a in accounts:
        has_child = any(other.startswith(a + ":") for other in account_set if other != a)
        out.append({"name": a, "is_parent": has_child, "is_leaf": not has_child})
    return out


def _posting_meta(posting: data.Posting) -> dict[str, Any]:
    meta = {}
    if posting.meta:
        for k, v in posting.meta.items():
            if not str(k).startswith("_"):
                meta[str(k)] = v
    return meta


def get_transactions(
    path: str | Path,
    start: date | None = None,
    end: date | None = None,
    class_tag: str | None = None,
    location: str | None = None,
) -> list[dict[str, Any]]:
    result = load_ledger(path)
    if not result.ok:
        raise LedgerError("Ledger has errors", result.errors)

    rows: list[dict[str, Any]] = []
    for entry in result.entries:
        if not isinstance(entry, data.Transaction):
            continue
        if start and entry.date < start:
            continue
        if end and entry.date > end:
            continue

        if class_tag or location:
            matched = False
            for p in entry.postings:
                meta = _posting_meta(p)
                if class_tag and meta.get("class") != class_tag:
                    continue
                if location and meta.get("location") != location:
                    continue
                matched = True
                break
            if not matched:
                continue

        postings = []
        for p in entry.postings:
            amt = p.units.number if p.units else None
            meta = _posting_meta(p)
            postings.append(
                {
                    "account": p.account,
                    "amount": str(money(amt)) if amt is not None else None,
                    "currency": p.units.currency if p.units else "USD",
                    "meta": meta,
                }
            )

        meta = {}
        if entry.meta:
            for k, v in entry.meta.items():
                if not str(k).startswith("_"):
                    meta[str(k)] = v
        rows.append(
            {
                "date": entry.date.isoformat(),
                "payee": entry.payee or "",
                "narration": entry.narration or "",
                "flag": entry.flag,
                "postings": postings,
                "meta": meta,
            }
        )
    return rows


def trial_balance(path: str | Path, as_of: date | None = None) -> list[dict[str, Any]]:
    result = load_ledger(path)
    if not result.ok:
        raise LedgerError("Ledger has errors", result.errors)

    entries = result.entries
    if as_of:
        entries = [e for e in entries if not hasattr(e, "date") or e.date <= as_of]

    root = realization.realize(entries)
    rows: list[dict[str, Any]] = []

    def walk(real_account: realization.RealAccount) -> None:
        account = real_account.account
        if account:
            for position in real_account.balance:
                number = position.units.number
                currency = position.units.currency
                if number == 0:
                    continue
                rows.append(
                    {
                        "account": account,
                        "currency": currency,
                        "balance": str(money(number)),
                    }
                )
        for child in real_account.values():
            walk(child)

    walk(root)
    rows.sort(key=lambda r: r["account"])
    return rows


def export_trial_balance_csv(path: str | Path) -> str:
    rows = trial_balance(path)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["account", "currency", "balance"])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def export_trial_balance_xlsx(path: str | Path) -> bytes:
    rows = trial_balance(path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Trial Balance"
    ws.append(["Account", "Currency", "Balance"])
    for r in rows:
        ws.append([r["account"], r["currency"], r["balance"]])
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def posted_fingerprints(path: str | Path) -> set[str]:
    """Fingerprints of posted txs: date|amount|normalized_payee."""
    fps: set[str] = set()
    try:
        txs = get_transactions(path)
    except LedgerError:
        return fps
    for tx in txs:
        payee = normalize_payee(tx.get("payee") or "")
        # bank-side amount is typically the asset posting absolute value
        for p in tx["postings"]:
            if p["account"].startswith("Assets:") or p["account"].startswith("Liabilities:"):
                amt = p["amount"]
                if amt:
                    fps.add(f"{tx['date']}|{money(amt)}|{payee}")
                    fps.add(f"{tx['date']}|{money(abs(money(amt)))}|{payee}")
    return fps


def normalize_payee(payee: str) -> str:
    s = payee.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    # strip common suffixes / store numbers
    s = re.sub(r"\b\d{3,}\b", "", s)
    return s.strip()
