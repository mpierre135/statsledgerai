"""Project paths."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
FIRM_CLIENTS = DATA / "firm" / "clients"
UPLOADS = DATA / "uploads"
DICTIONARIES = DATA / "dictionaries"
APP_DB = DATA / "app.db"
FRONTEND_DIST = ROOT / "frontend" / "dist"


def ensure_dirs() -> None:
    for d in (FIRM_CLIENTS, UPLOADS, DICTIONARIES, DATA / "firm"):
        d.mkdir(parents=True, exist_ok=True)
