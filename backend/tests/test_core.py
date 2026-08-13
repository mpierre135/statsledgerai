"""Core unit tests for StatsLedger AI."""

from __future__ import annotations

import shutil
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from app.money import D, allocate, assert_no_float, money
from app.ledger.service import (
    LedgerError,
    append_transaction,
    format_transaction,
    load_ledger,
    normalize_payee,
    trial_balance,
)
from app.bank import CsvOfxSource
from app.classify import classify_row, layer3_global
from app.bank import BankRow
from app.close import detect_accrual_candidates
from app.advisory import reasonable_comp
from app.tax import book_to_tax_grid
from app.tax import constants_2025 as C
from app.portal import detect_mime, save_upload
from app import db
from app.paths import FIRM_CLIENTS, ROOT, ensure_dirs
from app.seed import seed


@pytest.fixture(scope="module", autouse=True)
def _seed():
    ensure_dirs()
    seed()


def test_no_float_allowed():
    with pytest.raises(TypeError):
        money(1.23)  # type: ignore
    with pytest.raises(TypeError):
        assert_no_float(1.5)


def test_allocate_remainder_in_final_month():
    parts = allocate(money("1000.00"), 12)
    assert len(parts) == 12
    assert sum(parts) == money("1000.00")
    assert parts[0] == money("83.33")
    assert parts[-1] == money("83.37")  # absorbs remainder


def test_format_transaction_must_balance():
    with pytest.raises(LedgerError):
        format_transaction(
            date(2025, 1, 1),
            "Test",
            "unbalanced",
            [
                {"account": "Expenses:Meals", "amount": money("10.00")},
                {"account": "Assets:Bank:Checking", "amount": money("-9.00")},
            ],
        )


def test_seeded_ledgers_load_clean():
    for name in ("harbor_lemon.beancount", "northside_rentals.beancount"):
        result = load_ledger(FIRM_CLIENTS / name)
        assert result.ok, result.errors


def test_append_preserves_comments(tmp_path: Path):
    src = FIRM_CLIENTS / "harbor_lemon.beancount"
    dest = tmp_path / "harbor.beancount"
    shutil.copy(src, dest)
    before = dest.read_text()
    assert "Hand-written comment" in before
    append_transaction(
        dest,
        date(2025, 6, 1),
        [
            {"account": "Expenses:Meals", "amount": money("12.00")},
            {"account": "Assets:Bank:Checking", "amount": money("-12.00")},
        ],
        payee="Cafe",
        narration="append test",
    )
    after = dest.read_text()
    assert "Hand-written comment" in after
    assert "Cafe" in after
    result = load_ledger(dest)
    assert result.ok


def test_lock_date_blocks_writes(tmp_path: Path):
    src = FIRM_CLIENTS / "harbor_lemon.beancount"
    dest = tmp_path / "harbor.beancount"
    shutil.copy(src, dest)
    with pytest.raises(LedgerError, match="Period locked"):
        append_transaction(
            dest,
            date(2025, 1, 15),
            [
                {"account": "Expenses:Meals", "amount": money("5.00")},
                {"account": "Assets:Bank:Checking", "amount": money("-5.00")},
            ],
            payee="X",
            close_date="2025-03-31",
        )


def test_csv_import_and_classify():
    csv = b"""Date,Description,Amount\n2025-05-01,AMAZON MKTPLACE,-54.33\n"""
    rows = CsvOfxSource().extract(csv, "bank.csv")
    assert len(rows) == 1
    assert rows[0].payee.startswith("AMAZON")
    client = db.get_client("harbor_lemon")
    assert client
    result = classify_row(client["id"], client["beancount_path"], rows[0], threshold=85)
    assert result.account
    assert result.reason
    assert result.layer


def test_layer3_caps_confidence():
    row = BankRow(date(2025, 1, 1), money("-10"), "Completely Unknown ZZZ")
    r = layer3_global(row)
    assert r.confidence <= 68 or r.account == "Expenses:Uncategorized"


def test_firm_layer_amazon():
    # Harbor Amazon history + Northside Amazon should help classify
    row = BankRow(date(2025, 5, 1), money("-50"), "Amazon")
    client = db.get_client("harbor_lemon")
    assert client
    result = classify_row(client["id"], client["beancount_path"], row, threshold=50)
    assert "Office" in (result.account or "") or result.confidence >= 50


def test_meals_50_percent():
    client = db.get_client("harbor_lemon")
    assert client
    grid = book_to_tax_grid(client["id"], client["beancount_path"], "sole_prop")
    meals = next(l for l in grid["lines"] if l["tax_line"] == "C-24b")
    book = money(meals["book_amount"])
    tax = money(meals["tax_amount"])
    assert tax == money(book * C.MEALS_DEDUCTIBLE_PCT)


def test_accrual_schedule_sums():
    client = db.get_client("harbor_lemon")
    assert client
    cands = detect_accrual_candidates(client["beancount_path"])
    assert cands
    total = money(cands[0]["total"])
    parts = [money(s["amount"]) for s in cands[0]["schedule"]]
    assert sum(parts) == total


def test_reasonable_comp_s_corp_only():
    blocked = reasonable_comp("100000", "2000", "GEN", "sole_prop")
    assert blocked["enabled"] is False
    ok = reasonable_comp("145000", "1800", "531110", "s_corp")
    assert ok["enabled"] is True
    assert money(ok["recommended_salary"]) > 0


def test_token_hash_and_revoke():
    raw, row = db.create_magic_token("harbor_lemon", label="test", days=1)
    assert db.verify_magic_token(raw)
    db.revoke_token(row["id"])
    assert db.verify_magic_token(raw) is None


def test_upload_magic_bytes(tmp_path: Path, monkeypatch):
    from app import portal

    monkeypatch.setattr(portal, "UPLOADS", tmp_path)
    with pytest.raises(ValueError):
        save_upload("harbor_lemon", b"not a real file", "x.txt")
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    assert detect_mime(png) == "image/png"
    result = save_upload("harbor_lemon", png, "starbucks_lunch.png")
    assert result["extracted"]["merchant"] == "Starbucks"


def test_trial_balance_runs():
    client = db.get_client("harbor_lemon")
    assert client
    rows = trial_balance(client["beancount_path"])
    assert any(r["account"].startswith("Assets:Bank") for r in rows)


def test_import_dedup_fingerprint():
    fp = "2025-05-01|54.33|amazon mktplace"
    db.add_fingerprint("harbor_lemon", fp)
    assert db.fingerprint_exists("harbor_lemon", fp)
