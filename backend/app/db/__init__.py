"""SQLite app-state schema and accessors."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Generator, Iterable, Optional

from app.paths import APP_DB, ensure_dirs

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('sole_prop','s_corp','partnership')),
    beancount_path TEXT NOT NULL,
    confidence_threshold INTEGER NOT NULL DEFAULT 85,
    close_date TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS review_inbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    tx_date TEXT NOT NULL,
    amount TEXT NOT NULL,
    payee TEXT,
    narration TEXT,
    suggested_account TEXT,
    confidence INTEGER,
    layer TEXT,
    reason TEXT,
    fingerprint TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    source_import_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS classification_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    payee TEXT,
    amount TEXT,
    chosen_account TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS import_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, fingerprint),
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS magic_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    label TEXT,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS token_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_prefix TEXT,
    ip TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS needs_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    tx_ref TEXT,
    payee TEXT,
    amount TEXT,
    tx_date TEXT,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS staged_edits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    token_id INTEGER,
    inbox_id INTEGER,
    needs_info_id INTEGER,
    memo TEXT,
    suggested_category TEXT,
    receipt_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS document_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    doc_type TEXT NOT NULL,
    label TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    received INTEGER NOT NULL DEFAULT 0,
    file_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS prior_year_tax (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(client_id, tax_year),
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS tax_savings_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    tax_year INTEGER NOT NULL,
    strategy TEXT NOT NULL,
    savings TEXT NOT NULL,
    liability_current TEXT,
    liability_optimized TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    original_name TEXT,
    mime TEXT,
    size INTEGER,
    extracted_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(client_id) REFERENCES clients(id)
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@contextmanager
def connect() -> Generator[sqlite3.Connection, None, None]:
    ensure_dirs()
    conn = sqlite3.connect(APP_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


# --- clients ---

def upsert_client(
    client_id: str,
    name: str,
    entity_type: str,
    beancount_path: str,
    confidence_threshold: int = 85,
) -> None:
    with connect() as conn:
        existing = conn.execute("SELECT id FROM clients WHERE id=?", (client_id,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE clients SET name=?, entity_type=?, beancount_path=?, confidence_threshold=?
                   WHERE id=?""",
                (name, entity_type, beancount_path, confidence_threshold, client_id),
            )
        else:
            conn.execute(
                """INSERT INTO clients (id, name, entity_type, beancount_path, confidence_threshold, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (client_id, name, entity_type, beancount_path, confidence_threshold, iso()),
            )


def list_clients() -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(conn.execute("SELECT * FROM clients ORDER BY name").fetchall())


def get_client(client_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone())


def set_close_date(client_id: str, close_date: str | None) -> None:
    with connect() as conn:
        conn.execute("UPDATE clients SET close_date=? WHERE id=?", (close_date, client_id))


# --- review inbox ---

def add_inbox_item(item: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO review_inbox
               (client_id, tx_date, amount, payee, narration, suggested_account, confidence,
                layer, reason, fingerprint, status, source_import_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item["client_id"],
                item["tx_date"],
                item["amount"],
                item.get("payee"),
                item.get("narration"),
                item.get("suggested_account"),
                item.get("confidence"),
                item.get("layer"),
                item.get("reason"),
                item.get("fingerprint"),
                item.get("status", "open"),
                item.get("source_import_id"),
                iso(),
            ),
        )
        return int(cur.lastrowid)


def list_inbox(client_id: str, status: str = "open") -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM review_inbox WHERE client_id=? AND status=? ORDER BY tx_date DESC, id DESC",
                (client_id, status),
            ).fetchall()
        )


def get_inbox_item(item_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("SELECT * FROM review_inbox WHERE id=?", (item_id,)).fetchone())


def update_inbox_status(item_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE review_inbox SET status=? WHERE id=?", (status, item_id))


# --- classification feedback ---

def add_feedback(client_id: str, payee: str | None, amount: str | None, chosen_account: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO classification_feedback (client_id, payee, amount, chosen_account, created_at)
               VALUES (?,?,?,?,?)""",
            (client_id, payee, amount, chosen_account, iso()),
        )


def list_feedback(client_id: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if client_id:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM classification_feedback WHERE client_id=? ORDER BY id DESC",
                    (client_id,),
                ).fetchall()
            )
        return rows_to_dicts(
            conn.execute("SELECT * FROM classification_feedback ORDER BY id DESC").fetchall()
        )


# --- import fingerprints ---

def fingerprint_exists(client_id: str, fingerprint: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM import_fingerprints WHERE client_id=? AND fingerprint=?",
            (client_id, fingerprint),
        ).fetchone()
        return row is not None


def add_fingerprint(client_id: str, fingerprint: str) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO import_fingerprints (client_id, fingerprint, created_at)
               VALUES (?,?,?)""",
            (client_id, fingerprint, iso()),
        )


# --- magic tokens ---

def create_magic_token(
    client_id: str,
    label: str | None = None,
    days: int = 7,
) -> tuple[str, dict[str, Any]]:
    raw = secrets.token_urlsafe(32)
    token_hash = hash_token(raw)
    expires = utcnow() + timedelta(days=days)
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO magic_tokens (client_id, token_hash, label, expires_at, created_at)
               VALUES (?,?,?,?,?)""",
            (client_id, token_hash, label, iso(expires), iso()),
        )
        row = conn.execute("SELECT * FROM magic_tokens WHERE id=?", (cur.lastrowid,)).fetchone()
    return raw, dict(row)


def list_tokens(client_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT id, client_id, label, expires_at, revoked_at, created_at FROM magic_tokens WHERE client_id=? ORDER BY id DESC",
                (client_id,),
            ).fetchall()
        )


def revoke_token(token_id: int) -> None:
    with connect() as conn:
        conn.execute("UPDATE magic_tokens SET revoked_at=? WHERE id=?", (iso(), token_id))


def record_token_attempt(token_prefix: str, ip: str | None) -> int:
    with connect() as conn:
        conn.execute(
            "INSERT INTO token_attempts (token_prefix, ip, created_at) VALUES (?,?,?)",
            (token_prefix, ip, iso()),
        )
        since = iso(utcnow() - timedelta(minutes=15))
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM token_attempts WHERE token_prefix=? AND created_at>=?",
            (token_prefix, since),
        ).fetchone()["c"]
        return int(count)


def verify_magic_token(raw_token: str, ip: str | None = None) -> dict[str, Any] | None:
    prefix = raw_token[:8] if raw_token else ""
    attempts = record_token_attempt(prefix, ip)
    if attempts > 30:
        return None
    th = hash_token(raw_token)
    with connect() as conn:
        row = conn.execute("SELECT * FROM magic_tokens WHERE token_hash=?", (th,)).fetchone()
        if not row:
            return None
        data = dict(row)
        if data.get("revoked_at"):
            return None
        expires = datetime.fromisoformat(data["expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < utcnow():
            return None
        return data


# --- needs info ---

def add_needs_info(client_id: str, question: str, **kwargs: Any) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO needs_info
               (client_id, tx_ref, payee, amount, tx_date, question, status, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                client_id,
                kwargs.get("tx_ref"),
                kwargs.get("payee"),
                kwargs.get("amount"),
                kwargs.get("tx_date"),
                question,
                "open",
                iso(),
            ),
        )
        return int(cur.lastrowid)


def list_needs_info(client_id: str, status: str = "open") -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM needs_info WHERE client_id=? AND status=? ORDER BY id DESC",
                (client_id, status),
            ).fetchall()
        )


def update_needs_info_status(item_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE needs_info SET status=? WHERE id=?", (status, item_id))


# --- staged edits ---

def add_staged_edit(edit: dict[str, Any]) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO staged_edits
               (client_id, token_id, inbox_id, needs_info_id, memo, suggested_category,
                receipt_path, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                edit["client_id"],
                edit.get("token_id"),
                edit.get("inbox_id"),
                edit.get("needs_info_id"),
                edit.get("memo"),
                edit.get("suggested_category"),
                edit.get("receipt_path"),
                edit.get("status", "pending"),
                iso(),
            ),
        )
        return int(cur.lastrowid)


def list_staged_edits(client_id: str, status: str = "pending") -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM staged_edits WHERE client_id=? AND status=? ORDER BY id DESC",
                (client_id, status),
            ).fetchall()
        )


def get_staged_edit(edit_id: int) -> dict[str, Any] | None:
    with connect() as conn:
        return row_to_dict(conn.execute("SELECT * FROM staged_edits WHERE id=?", (edit_id,)).fetchone())


def update_staged_edit_status(edit_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute("UPDATE staged_edits SET status=? WHERE id=?", (status, edit_id))


# --- documents / tax ---

def upsert_checklist_item(
    client_id: str,
    tax_year: int,
    doc_type: str,
    label: str,
    required: bool = True,
) -> None:
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM document_checklist WHERE client_id=? AND tax_year=? AND doc_type=?",
            (client_id, tax_year, doc_type),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE document_checklist SET label=?, required=? WHERE id=?",
                (label, 1 if required else 0, existing["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO document_checklist
                   (client_id, tax_year, doc_type, label, required, received, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (client_id, tax_year, doc_type, label, 1 if required else 0, 0, iso()),
            )


def list_checklist(client_id: str, tax_year: int) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM document_checklist WHERE client_id=? AND tax_year=? ORDER BY id",
                (client_id, tax_year),
            ).fetchall()
        )


def mark_checklist_received(client_id: str, tax_year: int, doc_type: str, file_path: str | None = None) -> bool:
    with connect() as conn:
        cur = conn.execute(
            """UPDATE document_checklist SET received=1, file_path=?
               WHERE client_id=? AND tax_year=? AND doc_type=?""",
            (file_path, client_id, tax_year, doc_type),
        )
        return cur.rowcount > 0


def save_prior_year(client_id: str, tax_year: int, payload: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO prior_year_tax (client_id, tax_year, payload_json, created_at)
               VALUES (?,?,?,?)
               ON CONFLICT(client_id, tax_year) DO UPDATE SET payload_json=excluded.payload_json""",
            (client_id, tax_year, json.dumps(payload), iso()),
        )


def get_prior_year(client_id: str, tax_year: int) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM prior_year_tax WHERE client_id=? AND tax_year=?",
            (client_id, tax_year),
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["payload"] = json.loads(data.pop("payload_json"))
        return data


def list_prior_years(client_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM prior_year_tax WHERE client_id=? ORDER BY tax_year DESC",
            (client_id,),
        ).fetchall()
        out = []
        for row in rows:
            data = dict(row)
            data["payload"] = json.loads(data.pop("payload_json"))
            out.append(data)
        return out


def add_tax_savings(
    client_id: str,
    tax_year: int,
    strategy: str,
    savings: str,
    liability_current: str | None = None,
    liability_optimized: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO tax_savings_history
               (client_id, tax_year, strategy, savings, liability_current, liability_optimized, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (client_id, tax_year, strategy, savings, liability_current, liability_optimized, iso()),
        )


def list_tax_savings(client_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        return rows_to_dicts(
            conn.execute(
                "SELECT * FROM tax_savings_history WHERE client_id=? ORDER BY tax_year, strategy",
                (client_id,),
            ).fetchall()
        )


def add_receipt(
    client_id: str,
    stored_name: str,
    original_name: str | None,
    mime: str | None,
    size: int,
    extracted: dict[str, Any] | None = None,
) -> int:
    with connect() as conn:
        cur = conn.execute(
            """INSERT INTO receipts
               (client_id, stored_name, original_name, mime, size, extracted_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                client_id,
                stored_name,
                original_name,
                mime,
                size,
                json.dumps(extracted or {}),
                iso(),
            ),
        )
        return int(cur.lastrowid)
