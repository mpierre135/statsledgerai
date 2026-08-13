"""Magic-link portal: tokens, uploads, staged edits, simulated vision."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

from app import db
from app.paths import DICTIONARIES, UPLOADS, ensure_dirs

MAX_UPLOAD_BYTES = 5 * 1024 * 1024

MAGIC = {
    b"%PDF": "application/pdf",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def detect_mime(content: bytes) -> str | None:
    for magic, mime in MAGIC.items():
        if content.startswith(magic):
            return mime
    return None


def save_upload(client_id: str, content: bytes, original_name: str) -> dict[str, Any]:
    ensure_dirs()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds 5MB limit")
    mime = detect_mime(content)
    if not mime:
        raise ValueError("Unsupported file type; only PDF/PNG/JPEG allowed")

    ext = { "application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg" }[mime]
    stored = f"{client_id}_{uuid.uuid4().hex}{ext}"
    path = UPLOADS / stored
    path.write_bytes(content)

    extracted = simulate_vision(original_name, content, mime)
    receipt_id = db.add_receipt(
        client_id=client_id,
        stored_name=stored,
        original_name=original_name,
        mime=mime,
        size=len(content),
        extracted=extracted,
    )
    return {
        "receipt_id": receipt_id,
        "stored_name": stored,
        "path": str(path),
        "mime": mime,
        "extracted": extracted,
    }


def simulate_vision(original_name: str, content: bytes, mime: str) -> dict[str, Any]:
    """Simulate AI vision using fixture map + naive PDF text / filename heuristics."""
    fixtures_path = DICTIONARIES / "receipt_fixtures.json"
    fixtures = {}
    if fixtures_path.exists():
        fixtures = json.loads(fixtures_path.read_text())

    # Never use original_name for filesystem paths — only matching
    name_key = Path(original_name).name.lower()
    for key, value in fixtures.items():
        if key.lower() in name_key:
            return {**value, "source": "fixture_map"}

    text = ""
    if mime == "application/pdf":
        # naive extract printable strings
        try:
            text = content.decode("latin-1", errors="ignore")
        except Exception:
            text = ""
        printable = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in text)
        text = re.sub(r"\s+", " ", printable)

    merchant = None
    amount = None
    date_str = None

    m = re.search(r"(Amazon|Starbucks|Stripe|Shell|Uber|Adobe|Google|Microsoft)", text or name_key, re.I)
    if m:
        merchant = m.group(1)
    amt = re.search(r"\$?\s*(\d+\.\d{2})", text or name_key)
    if amt:
        amount = amt.group(1)
    dt = re.search(r"(20\d{2}-\d{2}-\d{2})", text or name_key)
    if dt:
        date_str = dt.group(1)

    return {
        "merchant": merchant,
        "amount": amount,
        "date": date_str,
        "source": "simulated",
        "raw_snippet": (text or "")[:200],
    }


def portal_queue(client_id: str) -> dict[str, Any]:
    inbox = db.list_inbox(client_id, status="open")
    needs = db.list_needs_info(client_id, status="open")
    # simplified categories for clients
    categories = [
        "Office Supplies",
        "Meals & Entertainment",
        "Travel",
        "Advertising",
        "Software / SaaS",
        "Utilities",
        "Insurance",
        "Professional Fees",
        "Cost of Goods Sold",
        "Automobile",
        "Rent",
        "Other / Not sure",
    ]
    return {
        "uncategorized": [
            {
                "id": i["id"],
                "type": "uncategorized",
                "date": i["tx_date"],
                "amount": i["amount"],
                "payee": i["payee"],
                "narration": i["narration"],
                "reason": i["reason"],
            }
            for i in inbox
        ],
        "needs_info": [
            {
                "id": n["id"],
                "type": "needs_info",
                "date": n.get("tx_date"),
                "amount": n.get("amount"),
                "payee": n.get("payee"),
                "question": n["question"],
            }
            for n in needs
        ],
        "categories": categories,
    }


CATEGORY_TO_ACCOUNT = {
    "Office Supplies": "Expenses:Office:Supplies",
    "Meals & Entertainment": "Expenses:Meals",
    "Travel": "Expenses:Travel",
    "Advertising": "Expenses:Advertising",
    "Software / SaaS": "Expenses:Software",
    "Utilities": "Expenses:Utilities",
    "Insurance": "Expenses:Insurance",
    "Professional Fees": "Expenses:ProfessionalFees",
    "Cost of Goods Sold": "Expenses:COGS",
    "Automobile": "Expenses:Automobile",
    "Rent": "Expenses:Rent",
    "Other / Not sure": "Expenses:Uncategorized",
}
