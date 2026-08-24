"""StatsLedger AI FastAPI application."""

from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure backend/ is on path when running as module
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import db
from app.advisory import reasonable_comp, tax_savings_report
from app.bank import BankRow, CsvOfxSource
from app.classify import classify_rows
from app.close import close_checklist, detect_accrual_candidates, detect_anomalies, payee_groups
from app.ledger.service import (
    LedgerError,
    add_account,
    append_transaction,
    export_trial_balance_csv,
    export_trial_balance_xlsx,
    get_accounts,
    get_transactions,
    load_ledger,
    posted_fingerprints,
    trial_balance,
)
from app.money import money as to_money
from app.paths import FRONTEND_DIST, ensure_dirs
from app.portal import CATEGORY_TO_ACCOUNT, portal_queue, save_upload
from app.seed import seed
from app.tax import book_to_tax_grid, generate_lead_sheet, ingest_prior_year, sort_documents

app = FastAPI(title="StatsLedger AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_dirs()
    db.init_db()
    if not db.list_clients():
        seed()


def _client_or_404(client_id: str) -> dict[str, Any]:
    client = db.get_client(client_id)
    if not client:
        raise HTTPException(404, f"Client not found: {client_id}")
    return client


def _ledger_http(err: LedgerError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"message": err.message, "errors": err.errors, "code": "ledger_error"},
    )


# ---------- Health / seed ----------

@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "statsledger-ai"}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/seed")
def api_seed() -> dict[str, Any]:
    return seed()


# ---------- Clients ----------

@app.get("/api/clients")
def api_clients() -> list[dict[str, Any]]:
    return db.list_clients()


@app.get("/api/clients/{client_id}")
def api_client(client_id: str) -> dict[str, Any]:
    client = _client_or_404(client_id)
    result = load_ledger(client["beancount_path"])
    return {
        **client,
        "ledger_ok": result.ok,
        "ledger_errors": result.errors,
    }


# ---------- Ledger ----------

@app.get("/api/clients/{client_id}/ledger/status")
def api_ledger_status(client_id: str) -> dict[str, Any]:
    client = _client_or_404(client_id)
    result = load_ledger(client["beancount_path"])
    return {"ok": result.ok, "errors": result.errors, "path": result.path}


@app.get("/api/clients/{client_id}/accounts")
def api_accounts(client_id: str) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return get_accounts(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)


class AddAccountBody(BaseModel):
    account: str
    open_date: Optional[str] = None


@app.post("/api/clients/{client_id}/accounts")
def api_add_account(client_id: str, body: AddAccountBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    try:
        od = date.fromisoformat(body.open_date) if body.open_date else date.today()
        result = add_account(client["beancount_path"], body.account, od)
        return {"ok": True, "accounts": get_accounts(client["beancount_path"])}
    except LedgerError as e:
        raise _ledger_http(e)


@app.get("/api/clients/{client_id}/transactions")
def api_transactions(
    client_id: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    class_tag: Optional[str] = None,
    location: Optional[str] = None,
) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return get_transactions(
            client["beancount_path"],
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
            class_tag=class_tag,
            location=location,
        )
    except LedgerError as e:
        raise _ledger_http(e)


@app.get("/api/clients/{client_id}/trial-balance")
def api_trial_balance(client_id: str) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return trial_balance(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)


@app.get("/api/clients/{client_id}/export/trial-balance.csv")
def api_export_csv(client_id: str) -> Response:
    client = _client_or_404(client_id)
    try:
        content = export_trial_balance_csv(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)
    return Response(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{client_id}_trial_balance.csv"'},
    )


@app.get("/api/clients/{client_id}/export/trial-balance.xlsx")
def api_export_xlsx(client_id: str) -> Response:
    client = _client_or_404(client_id)
    try:
        content = export_trial_balance_xlsx(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{client_id}_trial_balance.xlsx"'},
    )


class PostingIn(BaseModel):
    account: str
    amount: str
    class_tag: Optional[str] = Field(None, alias="class")
    location: Optional[str] = None

    model_config = {"populate_by_name": True}


class JournalEntryBody(BaseModel):
    date: str
    payee: Optional[str] = None
    narration: Optional[str] = None
    postings: list[PostingIn]
    meta: Optional[dict[str, Any]] = None


@app.post("/api/clients/{client_id}/journal")
def api_journal(client_id: str, body: JournalEntryBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    postings = []
    for p in body.postings:
        item: dict[str, Any] = {"account": p.account, "amount": to_money(p.amount)}
        if p.class_tag:
            item["class"] = p.class_tag
        if p.location:
            item["location"] = p.location
        postings.append(item)
    try:
        append_transaction(
            client["beancount_path"],
            date.fromisoformat(body.date),
            postings,
            payee=body.payee,
            narration=body.narration,
            meta=body.meta,
            close_date=client.get("close_date"),
        )
        return {"ok": True}
    except LedgerError as e:
        raise _ledger_http(e)
    except TypeError as e:
        raise HTTPException(400, str(e))


# ---------- Classify / Import ----------

@app.post("/api/clients/{client_id}/import/preview")
async def api_import_preview(client_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    client = _client_or_404(client_id)
    content = await file.read()
    source = CsvOfxSource()
    try:
        rows = source.extract(content, file.filename or "bank.csv")
    except Exception as e:
        raise HTTPException(400, f"Failed to parse bank file: {e}")

    try:
        fps = posted_fingerprints(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)

    classified = classify_rows(
        client_id,
        client["beancount_path"],
        rows,
        threshold=int(client.get("confidence_threshold") or 85),
        known_fps=fps,
    )
    return {
        "filename": file.filename,
        "count": len(classified),
        "rows": classified,
        "threshold": client.get("confidence_threshold", 85),
    }


class AcceptRow(BaseModel):
    date: str
    amount: str
    payee: str
    narration: Optional[str] = ""
    account: str
    fingerprint: str
    force_duplicate: bool = False
    class_tag: Optional[str] = None
    location: Optional[str] = None


class AcceptImportBody(BaseModel):
    rows: list[AcceptRow]
    bank_account: str = "Assets:Bank:Checking"


@app.post("/api/clients/{client_id}/import/accept")
def api_import_accept(client_id: str, body: AcceptImportBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    posted = 0
    skipped = 0
    inbox_ids = []
    # Ensure bank account exists for this client
    bank = body.bank_account
    if client_id == "northside_rentals" and bank == "Assets:Bank:Checking":
        bank = "Assets:Bank:Operating"

    for row in body.rows:
        if db.fingerprint_exists(client_id, row.fingerprint) and not row.force_duplicate:
            skipped += 1
            continue
        amt = to_money(row.amount)
        # bank posting mirrors signed amount; expense gets opposite
        expense_amt = to_money(-amt)
        bank_amt = to_money(amt)
        postings = [
            {"account": row.account, "amount": expense_amt},
            {"account": bank, "amount": bank_amt},
        ]
        if row.class_tag:
            postings[0]["class"] = row.class_tag
        if row.location:
            postings[0]["location"] = row.location
        try:
            add_account(client["beancount_path"], row.account)
            append_transaction(
                client["beancount_path"],
                date.fromisoformat(row.date),
                postings,
                payee=row.payee,
                narration=row.narration,
                meta={"fingerprint": row.fingerprint},
                close_date=client.get("close_date"),
            )
            db.add_fingerprint(client_id, row.fingerprint)
            db.add_feedback(client_id, row.payee, row.amount, row.account)
            posted += 1
        except LedgerError as e:
            raise _ledger_http(e)

    return {"posted": posted, "skipped_duplicates": skipped, "inbox_ids": inbox_ids}


class SendInboxBody(BaseModel):
    rows: list[dict[str, Any]]


@app.post("/api/clients/{client_id}/import/to-inbox")
def api_import_to_inbox(client_id: str, body: SendInboxBody) -> dict[str, Any]:
    _client_or_404(client_id)
    ids = []
    for row in body.rows:
        cls = row.get("classification") or {}
        item_id = db.add_inbox_item(
            {
                "client_id": client_id,
                "tx_date": row["date"],
                "amount": row["amount"],
                "payee": row.get("payee"),
                "narration": row.get("narration"),
                "suggested_account": cls.get("account"),
                "confidence": cls.get("confidence"),
                "layer": cls.get("layer"),
                "reason": cls.get("reason"),
                "fingerprint": row.get("fingerprint"),
            }
        )
        ids.append(item_id)
    return {"created": len(ids), "ids": ids}


@app.get("/api/clients/{client_id}/inbox")
def api_inbox(client_id: str) -> list[dict[str, Any]]:
    _client_or_404(client_id)
    return db.list_inbox(client_id)


class ResolveInboxBody(BaseModel):
    account: str
    bank_account: Optional[str] = None
    class_tag: Optional[str] = None
    location: Optional[str] = None
    narration: Optional[str] = None


@app.post("/api/clients/{client_id}/inbox/{item_id}/accept")
def api_inbox_accept(client_id: str, item_id: int, body: ResolveInboxBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    item = db.get_inbox_item(item_id)
    if not item or item["client_id"] != client_id:
        raise HTTPException(404, "Inbox item not found")

    bank = body.bank_account or (
        "Assets:Bank:Operating" if client_id == "northside_rentals" else "Assets:Bank:Checking"
    )
    amt = to_money(item["amount"])
    postings = [
        {"account": body.account, "amount": to_money(-amt)},
        {"account": bank, "amount": to_money(amt)},
    ]
    if body.class_tag:
        postings[0]["class"] = body.class_tag
    if body.location:
        postings[0]["location"] = body.location
    try:
        add_account(client["beancount_path"], body.account)
        append_transaction(
            client["beancount_path"],
            date.fromisoformat(item["tx_date"]),
            postings,
            payee=item.get("payee"),
            narration=body.narration or item.get("narration"),
            meta={"fingerprint": item.get("fingerprint"), "from_inbox": str(item_id)},
            close_date=client.get("close_date"),
        )
    except LedgerError as e:
        raise _ledger_http(e)

    if item.get("fingerprint"):
        db.add_fingerprint(client_id, item["fingerprint"])
    db.add_feedback(client_id, item.get("payee"), item.get("amount"), body.account)
    db.update_inbox_status(item_id, "posted")
    return {"ok": True}


# ---------- Close / QA ----------

@app.get("/api/clients/{client_id}/close/payees")
def api_payees(client_id: str, start: Optional[str] = None, end: Optional[str] = None) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return payee_groups(
            client["beancount_path"],
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
        )
    except LedgerError as e:
        raise _ledger_http(e)


@app.get("/api/clients/{client_id}/close/anomalies")
def api_anomalies(client_id: str, start: Optional[str] = None, end: Optional[str] = None) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return detect_anomalies(
            client["beancount_path"],
            start=date.fromisoformat(start) if start else None,
            end=date.fromisoformat(end) if end else None,
        )
    except LedgerError as e:
        raise _ledger_http(e)


class NeedsInfoBody(BaseModel):
    question: str
    tx_ref: Optional[str] = None
    payee: Optional[str] = None
    amount: Optional[str] = None
    tx_date: Optional[str] = None


@app.post("/api/clients/{client_id}/close/needs-info")
def api_flag_needs_info(client_id: str, body: NeedsInfoBody) -> dict[str, Any]:
    _client_or_404(client_id)
    item_id = db.add_needs_info(
        client_id,
        body.question,
        tx_ref=body.tx_ref,
        payee=body.payee,
        amount=body.amount,
        tx_date=body.tx_date,
    )
    return {"id": item_id}


@app.get("/api/clients/{client_id}/close/checklist")
def api_close_checklist(client_id: str, period_end: str) -> dict[str, Any]:
    client = _client_or_404(client_id)
    try:
        return close_checklist(client["beancount_path"], date.fromisoformat(period_end))
    except LedgerError as e:
        raise _ledger_http(e)


class CloseMonthBody(BaseModel):
    period_end: str
    force: bool = False


@app.post("/api/clients/{client_id}/close/month")
def api_close_month(client_id: str, body: CloseMonthBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    try:
        checklist = close_checklist(client["beancount_path"], date.fromisoformat(body.period_end))
    except LedgerError as e:
        raise _ledger_http(e)
    if not checklist["can_close"] and not body.force:
        raise HTTPException(400, detail={"message": "Blocking anomalies remain", "checklist": checklist})
    db.set_close_date(client_id, body.period_end)
    return {"ok": True, "close_date": body.period_end, "checklist": checklist}


@app.get("/api/clients/{client_id}/close/accruals")
def api_accruals(client_id: str) -> list[dict[str, Any]]:
    client = _client_or_404(client_id)
    try:
        return detect_accrual_candidates(client["beancount_path"])
    except LedgerError as e:
        raise _ledger_http(e)


class ApproveAccrualBody(BaseModel):
    schedule: list[dict[str, Any]]
    expense_account: str
    prepaid_account: str = "Assets:Prepaid:Expenses"
    payee: Optional[str] = None
    up_to_date: Optional[str] = None


@app.post("/api/clients/{client_id}/close/accruals/approve")
def api_approve_accrual(client_id: str, body: ApproveAccrualBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    cutoff = date.fromisoformat(body.up_to_date) if body.up_to_date else date.today()
    posted = 0
    try:
        add_account(client["beancount_path"], body.expense_account)
        add_account(client["beancount_path"], body.prepaid_account)
        for row in body.schedule:
            d = date.fromisoformat(row["date"])
            if d > cutoff:
                continue
            amt = to_money(row["amount"])
            append_transaction(
                client["beancount_path"],
                d,
                [
                    {"account": body.expense_account, "amount": amt},
                    {"account": body.prepaid_account, "amount": to_money(-amt)},
                ],
                payee=body.payee or "Accrual amortization",
                narration=f"Amortization period {row.get('period_index')}",
                meta={"accrual": "true"},
                close_date=client.get("close_date"),
            )
            posted += 1
    except LedgerError as e:
        raise _ledger_http(e)
    return {"posted": posted}


# ---------- Portal tokens (firm side) ----------

class CreateTokenBody(BaseModel):
    label: Optional[str] = None
    days: int = 7


@app.post("/api/clients/{client_id}/portal/tokens")
def api_create_token(client_id: str, body: CreateTokenBody) -> dict[str, Any]:
    _client_or_404(client_id)
    raw, row = db.create_magic_token(client_id, label=body.label, days=body.days)
    return {"token": raw, "link_path": f"/portal/{raw}", **{k: row[k] for k in ("id", "expires_at", "label", "created_at")}}


@app.get("/api/clients/{client_id}/portal/tokens")
def api_list_tokens(client_id: str) -> list[dict[str, Any]]:
    _client_or_404(client_id)
    return db.list_tokens(client_id)


@app.post("/api/clients/{client_id}/portal/tokens/{token_id}/revoke")
def api_revoke_token(client_id: str, token_id: int) -> dict[str, Any]:
    _client_or_404(client_id)
    db.revoke_token(token_id)
    return {"ok": True}


@app.get("/api/clients/{client_id}/portal/staged")
def api_list_staged(client_id: str) -> list[dict[str, Any]]:
    _client_or_404(client_id)
    return db.list_staged_edits(client_id)


class ApproveStagedBody(BaseModel):
    account: Optional[str] = None
    bank_account: Optional[str] = None


@app.post("/api/clients/{client_id}/portal/staged/{edit_id}/approve")
def api_approve_staged(client_id: str, edit_id: int, body: ApproveStagedBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    edit = db.get_staged_edit(edit_id)
    if not edit or edit["client_id"] != client_id:
        raise HTTPException(404, "Staged edit not found")

    account = body.account
    if not account and edit.get("suggested_category"):
        account = CATEGORY_TO_ACCOUNT.get(edit["suggested_category"], "Expenses:Uncategorized")
    if not account:
        account = "Expenses:Uncategorized"

    # Prefer linked inbox row amounts
    payee = None
    amt = None
    tx_date = date.today()
    narration = edit.get("memo") or ""
    fingerprint = None

    if edit.get("inbox_id"):
        item = db.get_inbox_item(edit["inbox_id"])
        if item:
            payee = item.get("payee")
            amt = to_money(item["amount"])
            tx_date = date.fromisoformat(item["tx_date"])
            fingerprint = item.get("fingerprint")
            if not narration:
                narration = item.get("narration") or ""
            db.update_inbox_status(item["id"], "posted")

    if edit.get("needs_info_id"):
        ni = next((n for n in db.list_needs_info(client_id, "open") if n["id"] == edit["needs_info_id"]), None)
        if ni:
            payee = payee or ni.get("payee")
            if ni.get("amount"):
                amt = to_money(ni["amount"])
            if ni.get("tx_date"):
                tx_date = date.fromisoformat(ni["tx_date"])
            db.update_needs_info_status(ni["id"], "resolved")

    if amt is None:
        # memo-only needs-info with no amount — just mark approved
        db.update_staged_edit_status(edit_id, "approved")
        return {"ok": True, "posted": False}

    bank = body.bank_account or (
        "Assets:Bank:Operating" if client_id == "northside_rentals" else "Assets:Bank:Checking"
    )
    meta: dict[str, Any] = {"from_portal": str(edit_id)}
    if edit.get("receipt_path"):
        meta["receipt"] = edit["receipt_path"]
    if fingerprint:
        meta["fingerprint"] = fingerprint

    try:
        add_account(client["beancount_path"], account)
        append_transaction(
            client["beancount_path"],
            tx_date,
            [
                {"account": account, "amount": to_money(-amt)},
                {"account": bank, "amount": to_money(amt)},
            ],
            payee=payee,
            narration=narration,
            meta=meta,
            close_date=client.get("close_date"),
        )
    except LedgerError as e:
        raise _ledger_http(e)

    if fingerprint:
        db.add_fingerprint(client_id, fingerprint)
    db.add_feedback(client_id, payee, str(amt), account)
    db.update_staged_edit_status(edit_id, "approved")
    return {"ok": True, "posted": True}


# ---------- Public portal ----------

@app.get("/api/portal/{token}")
def api_portal_get(token: str, request: Request) -> dict[str, Any]:
    ip = request.client.host if request.client else None
    row = db.verify_magic_token(token, ip=ip)
    if not row:
        raise HTTPException(401, "Invalid, expired, or revoked link")
    client = db.get_client(row["client_id"])
    queue = portal_queue(row["client_id"])
    return {
        "client_name": client["name"] if client else row["client_id"],
        "client_id": row["client_id"],
        "expires_at": row["expires_at"],
        **queue,
    }


class PortalSubmitBody(BaseModel):
    inbox_id: Optional[int] = None
    needs_info_id: Optional[int] = None
    memo: Optional[str] = None
    category: Optional[str] = None
    receipt_stored_name: Optional[str] = None


@app.post("/api/portal/{token}/submit")
def api_portal_submit(token: str, body: PortalSubmitBody, request: Request) -> dict[str, Any]:
    ip = request.client.host if request.client else None
    row = db.verify_magic_token(token, ip=ip)
    if not row:
        raise HTTPException(401, "Invalid, expired, or revoked link")
    edit_id = db.add_staged_edit(
        {
            "client_id": row["client_id"],
            "token_id": row["id"],
            "inbox_id": body.inbox_id,
            "needs_info_id": body.needs_info_id,
            "memo": body.memo,
            "suggested_category": body.category,
            "receipt_path": body.receipt_stored_name,
        }
    )
    return {"ok": True, "staged_edit_id": edit_id}


@app.post("/api/portal/{token}/upload")
async def api_portal_upload(token: str, request: Request, file: UploadFile = File(...)) -> dict[str, Any]:
    ip = request.client.host if request.client else None
    row = db.verify_magic_token(token, ip=ip)
    if not row:
        raise HTTPException(401, "Invalid, expired, or revoked link")
    content = await file.read()
    try:
        result = save_upload(row["client_id"], content, file.filename or "upload.bin")
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


# ---------- Tax ----------

@app.post("/api/clients/{client_id}/tax/prior-year")
async def api_prior_year(client_id: str, request: Request) -> dict[str, Any]:
    _client_or_404(client_id)
    payload = await request.json()
    return ingest_prior_year(client_id, payload)


@app.get("/api/clients/{client_id}/tax/prior-years")
def api_list_prior(client_id: str) -> list[dict[str, Any]]:
    _client_or_404(client_id)
    return db.list_prior_years(client_id)


@app.get("/api/clients/{client_id}/tax/checklist")
def api_checklist(client_id: str, tax_year: int = 2025) -> list[dict[str, Any]]:
    _client_or_404(client_id)
    return db.list_checklist(client_id, tax_year)


@app.post("/api/clients/{client_id}/tax/docs")
async def api_tax_docs(client_id: str, tax_year: int = 2025, files: list[UploadFile] = File(...)) -> dict[str, Any]:
    _client_or_404(client_id)
    parsed = []
    for f in files:
        content = await f.read()
        parsed.append((f.filename or "doc.bin", content))
    results = sort_documents(client_id, tax_year, parsed)
    return {"results": results, "checklist": db.list_checklist(client_id, tax_year)}


@app.get("/api/clients/{client_id}/tax/book-to-tax")
def api_book_to_tax(client_id: str) -> dict[str, Any]:
    client = _client_or_404(client_id)
    try:
        return book_to_tax_grid(client_id, client["beancount_path"], client["entity_type"])
    except LedgerError as e:
        raise _ledger_http(e)


@app.get("/api/clients/{client_id}/tax/lead-sheet.xlsx")
def api_lead_sheet(client_id: str) -> Response:
    client = _client_or_404(client_id)
    try:
        content = generate_lead_sheet(client_id, client["beancount_path"], client["entity_type"])
    except LedgerError as e:
        raise _ledger_http(e)
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{client_id}_lead_sheet.xlsx"'},
    )


# ---------- Advisory ----------

class ReasonableCompBody(BaseModel):
    net_income: str
    hours_worked: str
    industry_code: str = "GEN"


@app.post("/api/clients/{client_id}/advisory/reasonable-comp")
def api_reasonable_comp(client_id: str, body: ReasonableCompBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    return reasonable_comp(body.net_income, body.hours_worked, body.industry_code, client["entity_type"])


class SavingsBody(BaseModel):
    net_income: str
    proposed_salary: Optional[str] = None
    augusta_days: int = 0
    augusta_daily_rate: str = "0"
    section_179: str = "0"
    qbi_eligible_income: Optional[str] = None


@app.post("/api/clients/{client_id}/advisory/savings")
def api_savings(client_id: str, body: SavingsBody) -> dict[str, Any]:
    client = _client_or_404(client_id)
    return tax_savings_report(
        client_id,
        client["entity_type"],
        body.net_income,
        proposed_salary=body.proposed_salary,
        augusta_days=body.augusta_days,
        augusta_daily_rate=body.augusta_daily_rate,
        section_179=body.section_179,
        qbi_eligible_income=body.qbi_eligible_income,
    )


@app.get("/api/advisory/industries")
def api_industries() -> list[dict[str, Any]]:
    from app.advisory import load_industry_wages

    return load_industry_wages()


# ---------- Static SPA ----------

if FRONTEND_DIST.exists():
    assets = FRONTEND_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
