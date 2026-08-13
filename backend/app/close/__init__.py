"""Auto-close QA, anomalies, accruals."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from typing import Any

from app.ledger.service import get_accounts, get_transactions, load_ledger, trial_balance
from app.money import allocate, money


PERIOD_RE = re.compile(
    r"for the period\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)


def payee_groups(path: str, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    txs = get_transactions(path, start=start, end=end)
    groups: dict[str, dict[str, Any]] = {}
    for tx in txs:
        payee = (tx.get("payee") or "Unknown").strip() or "Unknown"
        g = groups.setdefault(
            payee,
            {"payee": payee, "count": 0, "accounts": set(), "total": Decimal("0"), "transactions": []},
        )
        g["count"] += 1
        expense_accts = [
            p["account"]
            for p in tx["postings"]
            if p["account"].startswith("Expenses:") or p["account"].startswith("Income:")
        ]
        for a in expense_accts:
            g["accounts"].add(a)
        bank_amts = [
            money(p["amount"])
            for p in tx["postings"]
            if p["amount"] and (p["account"].startswith("Assets:") or p["account"].startswith("Liabilities:"))
        ]
        if bank_amts:
            g["total"] += abs(bank_amts[0])
        g["transactions"].append(tx)

    out = []
    for g in groups.values():
        accounts = sorted(g["accounts"])
        out.append(
            {
                "payee": g["payee"],
                "count": g["count"],
                "accounts": accounts,
                "mixed_accounts": len(accounts) > 1,
                "total": str(money(g["total"])),
                "transactions": g["transactions"],
            }
        )
    out.sort(key=lambda x: (-x["count"], x["payee"]))
    return out


def detect_anomalies(path: str, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    anomalies: list[dict[str, Any]] = []
    accounts = get_accounts(path)
    parent_names = {a["name"] for a in accounts if a["is_parent"]}
    txs = get_transactions(path, start=start, end=end)

    # 1. Negative bank balances
    for row in trial_balance(path):
        if row["account"].startswith("Assets:Bank") or row["account"].startswith("Assets:Cash"):
            bal = money(row["balance"])
            if bal < 0:
                anomalies.append(
                    {
                        "type": "negative_bank_balance",
                        "severity": "high",
                        "message": f"{row['account']} balance is {bal}",
                        "account": row["account"],
                        "amount": str(bal),
                    }
                )

    # 2. Multi-category inconsistencies by payee
    by_payee: dict[str, set[str]] = defaultdict(set)
    payee_txs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tx in txs:
        payee = (tx.get("payee") or "").strip()
        if not payee:
            continue
        for p in tx["postings"]:
            if p["account"].startswith("Expenses:"):
                by_payee[payee].add(p["account"])
                payee_txs[payee].append(tx)
    for payee, accts in by_payee.items():
        if len(accts) > 1:
            anomalies.append(
                {
                    "type": "multi_category",
                    "severity": "medium",
                    "message": f"{payee} coded to {len(accts)} expense accounts: {', '.join(sorted(accts))}",
                    "payee": payee,
                    "accounts": sorted(accts),
                }
            )

    # 3. Missing descriptions for > $1000
    for tx in txs:
        bank_amts = [
            abs(money(p["amount"]))
            for p in tx["postings"]
            if p["amount"] and (p["account"].startswith("Assets:") or p["account"].startswith("Liabilities:"))
        ]
        if not bank_amts:
            continue
        amt = max(bank_amts)
        if amt >= money("1000"):
            narr = (tx.get("narration") or "").strip()
            has_receipt = bool((tx.get("meta") or {}).get("receipt"))
            if not narr and not has_receipt:
                anomalies.append(
                    {
                        "type": "missing_description",
                        "severity": "medium",
                        "message": f"{tx['date']} {tx.get('payee')} ${amt} missing memo/receipt",
                        "payee": tx.get("payee"),
                        "date": tx["date"],
                        "amount": str(amt),
                        "tx_ref": f"{tx['date']}|{tx.get('payee')}|{amt}",
                    }
                )

    # 4. Parent-level booking
    for tx in txs:
        for p in tx["postings"]:
            if p["account"] in parent_names:
                anomalies.append(
                    {
                        "type": "parent_level_booking",
                        "severity": "low",
                        "message": f"{tx['date']} posted to parent account {p['account']}",
                        "account": p["account"],
                        "payee": tx.get("payee"),
                        "date": tx["date"],
                        "tx_ref": f"{tx['date']}|{tx.get('payee')}|{p['account']}",
                    }
                )

    return anomalies


def detect_accrual_candidates(path: str) -> list[dict[str, Any]]:
    txs = get_transactions(path)
    out = []
    for tx in txs:
        text = f"{tx.get('narration') or ''} {(tx.get('meta') or {}).get('accrual_period') or ''}"
        m = PERIOD_RE.search(text)
        tagged = (tx.get("meta") or {}).get("tag") == "accrual" or (tx.get("meta") or {}).get("accrual")
        if not m and not tagged:
            continue
        if m:
            start = date.fromisoformat(m.group(1))
            end = date.fromisoformat(m.group(2))
        else:
            # default 12 months from tx date
            start = date.fromisoformat(tx["date"])
            end = start + relativedelta(months=11)

        expense_acct = None
        prepaid_amt = None
        for p in tx["postings"]:
            if p["account"].startswith("Expenses:") or p["account"].startswith("Assets:Prepaid"):
                if p["amount"]:
                    prepaid_amt = abs(money(p["amount"]))
                if p["account"].startswith("Expenses:") or p["account"].startswith("Assets:Prepaid"):
                    expense_acct = p["account"]
            if p["account"].startswith("Assets:Prepaid"):
                expense_acct = expense_acct or "Expenses:Insurance"
                if p["amount"]:
                    prepaid_amt = abs(money(p["amount"]))

        if prepaid_amt is None:
            continue

        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        months = max(1, months)
        parts = allocate(prepaid_amt, months)
        schedule = []
        cur = start.replace(day=1)
        for i, part in enumerate(parts):
            schedule.append(
                {
                    "date": cur.isoformat(),
                    "amount": str(part),
                    "period_index": i + 1,
                }
            )
            cur = cur + relativedelta(months=1)

        out.append(
            {
                "source_date": tx["date"],
                "payee": tx.get("payee"),
                "narration": tx.get("narration"),
                "total": str(prepaid_amt),
                "periods": months,
                "expense_account": expense_acct or "Expenses:Insurance",
                "prepaid_account": "Assets:Prepaid:Expenses",
                "schedule": schedule,
            }
        )
    return out


def close_checklist(path: str, period_end: date) -> dict[str, Any]:
    start = period_end.replace(day=1)
    anomalies = detect_anomalies(path, start=start, end=period_end)
    blocking = [a for a in anomalies if a["severity"] in ("high", "medium")]
    return {
        "period_end": period_end.isoformat(),
        "anomaly_count": len(anomalies),
        "blocking_count": len(blocking),
        "can_close": len(blocking) == 0,
        "anomalies": anomalies,
    }
