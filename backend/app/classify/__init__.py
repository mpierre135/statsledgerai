"""Three-layer autoclassification cake."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from app.bank import BankRow
from app import db
from app.ledger.service import get_transactions, load_ledger, normalize_payee
from app.money import money
from app.paths import DICTIONARIES, FIRM_CLIENTS


@dataclass
class ClassificationResult:
    account: str | None
    confidence: int
    layer: str
    reason: str
    suggested_accounts: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account": self.account,
            "confidence": self.confidence,
            "layer": self.layer,
            "reason": self.reason,
            "suggested_accounts": self.suggested_accounts,
        }


def _load_global_dict() -> dict[str, Any]:
    path = DICTIONARIES / "global_merchants.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"merchants": {}, "keywords": {}}


def _expense_account_from_postings(postings: list[dict[str, Any]]) -> str | None:
    for p in postings:
        acct = p["account"]
        if acct.startswith("Expenses:") or acct.startswith("Income:") or acct.startswith("Assets:Fixed"):
            return acct
    for p in postings:
        if not p["account"].startswith("Assets:Bank") and not p["account"].startswith("Assets:Cash"):
            if not p["account"].startswith("Liabilities:"):
                return p["account"]
    return None


def _history_matches(
    client_id: str,
    beancount_path: str,
    payee: str,
    amount: Decimal,
) -> list[dict[str, Any]]:
    """Collect prior coding history for a payee from ledger + feedback."""
    norm = normalize_payee(payee)
    matches: list[dict[str, Any]] = []

    try:
        txs = get_transactions(beancount_path)
    except Exception:
        txs = []

    for tx in txs:
        tpayee = normalize_payee(tx.get("payee") or "")
        score = fuzz.token_set_ratio(norm, tpayee)
        if score < 70:
            continue
        acct = _expense_account_from_postings(tx["postings"])
        if not acct:
            continue
        # amount band: within 20% or same absolute amount
        bank_amts = [
            abs(money(p["amount"]))
            for p in tx["postings"]
            if p["amount"] and (p["account"].startswith("Assets:") or p["account"].startswith("Liabilities:"))
        ]
        amt_score = 0
        if bank_amts:
            target = abs(money(amount))
            closest = min(bank_amts, key=lambda a: abs(a - target))
            if target == 0:
                amt_score = 50
            else:
                ratio = float(min(closest, target) / max(closest, target))
                amt_score = int(ratio * 100)
        matches.append(
            {
                "payee": tx.get("payee"),
                "account": acct,
                "similarity": score,
                "amount_score": amt_score,
                "source": "ledger",
            }
        )

    for fb in db.list_feedback(client_id):
        fpayee = normalize_payee(fb.get("payee") or "")
        score = fuzz.token_set_ratio(norm, fpayee)
        if score < 70:
            continue
        matches.append(
            {
                "payee": fb.get("payee"),
                "account": fb["chosen_account"],
                "similarity": score,
                "amount_score": 80,
                "source": "feedback",
            }
        )
    return matches


def _score_from_matches(matches: list[dict[str, Any]], layer: str) -> ClassificationResult | None:
    if not matches:
        return None
    # group by account
    by_acct: dict[str, list[dict[str, Any]]] = {}
    for m in matches:
        by_acct.setdefault(m["account"], []).append(m)

    best_acct = max(by_acct.keys(), key=lambda a: (len(by_acct[a]), max(x["similarity"] for x in by_acct[a])))
    group = by_acct[best_acct]
    avg_sim = sum(m["similarity"] for m in group) / len(group)
    avg_amt = sum(m["amount_score"] for m in group) / len(group)
    unanimous = len(by_acct) == 1

    # exact-ish merchant + unanimous → high 90s
    if avg_sim >= 95 and unanimous:
        confidence = 97
    elif avg_sim >= 90 and unanimous:
        confidence = 93
    elif avg_sim >= 85:
        confidence = int(75 + avg_sim * 0.15 + (5 if unanimous else -8))
    else:
        confidence = int(55 + avg_sim * 0.25 + avg_amt * 0.05 + (5 if unanimous else -10))

    confidence = max(0, min(99, confidence))
    if not unanimous:
        # contradiction penalty already applied; cap under threshold often
        confidence = min(confidence, 82)

    reason = (
        f"{layer} — {len(group)} prior match(es) for similar payee, "
        f"{'all' if unanimous else 'mostly'} coded {best_acct} "
        f"(similarity {avg_sim:.0f}%)"
    )
    if not unanimous:
        others = ", ".join(a for a in by_acct if a != best_acct)
        reason += f"; also seen as {others}"

    return ClassificationResult(
        account=best_acct,
        confidence=confidence,
        layer=layer,
        reason=reason,
        suggested_accounts=list(by_acct.keys()),
    )


def layer1_client(client_id: str, beancount_path: str, row: BankRow) -> ClassificationResult | None:
    matches = _history_matches(client_id, beancount_path, row.payee, row.amount)
    # only this client's ledger + feedback already scoped
    return _score_from_matches(matches, "Layer 1 (Client)")


def layer2_firm(client_id: str, row: BankRow) -> ClassificationResult | None:
    matches: list[dict[str, Any]] = []
    for client in db.list_clients():
        if client["id"] == client_id:
            continue
        matches.extend(_history_matches(client["id"], client["beancount_path"], row.payee, row.amount))
    return _score_from_matches(matches, "Layer 2 (Firm)")


def layer3_global(row: BankRow) -> ClassificationResult:
    g = _load_global_dict()
    merchants = g.get("merchants", {})
    keywords = g.get("keywords", {})
    norm = normalize_payee(row.payee)
    text = f"{norm} {normalize_payee(row.narration)}"

    # exact merchant keys
    best_key = None
    best_score = 0
    for key, account in merchants.items():
        score = fuzz.partial_ratio(normalize_payee(key), norm)
        if score > best_score:
            best_score = score
            best_key = (key, account)

    if best_key and best_score >= 85:
        account = best_key[1]
        # dictionary fallback caps in the 60s
        confidence = min(68, 50 + best_score // 5)
        return ClassificationResult(
            account=account,
            confidence=confidence,
            layer="Layer 3 (Global)",
            reason=f"Layer 3 (Global) — merchant dictionary matched '{best_key[0]}' → {account}",
            suggested_accounts=[account],
        )

    for kw, account in keywords.items():
        if normalize_payee(kw) in text:
            return ClassificationResult(
                account=account,
                confidence=55,
                layer="Layer 3 (Global)",
                reason=f"Layer 3 (Global) — keyword '{kw}' → {account}",
                suggested_accounts=[account],
            )

    return ClassificationResult(
        account="Expenses:Uncategorized",
        confidence=20,
        layer="Layer 3 (Global)",
        reason="Layer 3 (Global) — no dictionary match; default Uncategorized",
        suggested_accounts=["Expenses:Uncategorized"],
    )


def classify_row(
    client_id: str,
    beancount_path: str,
    row: BankRow,
    threshold: int = 85,
) -> ClassificationResult:
    for fn in (
        lambda: layer1_client(client_id, beancount_path, row),
        lambda: layer2_firm(client_id, row),
    ):
        result = fn()
        if result and result.confidence >= threshold:
            return result
        if result and result.account and result.confidence >= 70:
            # keep as candidate but try next layer for higher confidence
            candidate = result
            next_result = None
            # continue cascade; if later is worse, return candidate
            # simplify: return first >= threshold else fall through
            pass
        if result and result.confidence >= threshold:
            return result

    l1 = layer1_client(client_id, beancount_path, row)
    if l1 and l1.confidence >= threshold:
        return l1
    l2 = layer2_firm(client_id, row)
    if l2 and l2.confidence >= threshold:
        return l2
    # return best of l1/l2 if better than global, else global
    l3 = layer3_global(row)
    best = l3
    for cand in (l1, l2):
        if cand and cand.confidence > best.confidence:
            best = cand
    return best


def classify_rows(
    client_id: str,
    beancount_path: str,
    rows: list[BankRow],
    threshold: int = 85,
    known_fps: set[str] | None = None,
) -> list[dict[str, Any]]:
    known_fps = known_fps or set()
    out = []
    for row in rows:
        result = classify_row(client_id, beancount_path, row, threshold=threshold)
        is_dup = row.fingerprint in known_fps or db.fingerprint_exists(client_id, row.fingerprint)
        needs_review = result.confidence < threshold or result.account == "Expenses:Uncategorized"
        out.append(
            {
                "date": row.tx_date.isoformat(),
                "amount": str(money(row.amount)),
                "payee": row.payee,
                "narration": row.narration,
                "fingerprint": row.fingerprint,
                "possible_duplicate": is_dup,
                "needs_review": needs_review,
                "classification": result.to_dict(),
            }
        )
    return out
