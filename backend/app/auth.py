"""Clerk session verification. Only mpierre135@gmail.com may call protected APIs."""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import httpx
import jwt
from jwt import PyJWKClient

ALLOWED_EMAIL = os.environ.get("ALLOWED_EMAIL", "mpierre135@gmail.com").lower()

_email_cache: dict[str, tuple[float, str]] = {}
_jwks_client: PyJWKClient | None = None


def _load_env_files() -> None:
    path = Path(__file__).resolve().parents[2] / "backend" / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_files()


def _issuer() -> str:
    explicit = os.environ.get("CLERK_ISSUER", "").strip()
    if explicit:
        return explicit.rstrip("/")
    pk = os.environ.get("CLERK_PUBLISHABLE_KEY") or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY") or ""
    if not pk:
        raise RuntimeError("CLERK_PUBLISHABLE_KEY is not set")
    payload = pk.split("_", 2)[-1]
    padded = payload + "=" * (-len(payload) % 4)
    host = base64.b64decode(padded).decode("utf-8").rstrip("$")
    return f"https://{host}"


def _jwks() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(f"{_issuer()}/.well-known/jwks.json")
    return _jwks_client


def is_public_path(path: str, method: str) -> bool:
    if method == "OPTIONS":
        return True
    if path in {"/", "/api/health"}:
        return True
    if path.startswith("/api/portal/"):
        return True
    if path.startswith("/assets/"):
        return True
    return False


def verify_session_token(token: str) -> dict[str, Any]:
    signing_key = _jwks().get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=_issuer(),
        options={"verify_aud": False},
    )


def email_for_user(user_id: str) -> str:
    cached = _email_cache.get(user_id)
    now = time.time()
    if cached and cached[0] > now:
        return cached[1]
    secret = os.environ.get("CLERK_SECRET_KEY", "")
    if not secret:
        raise RuntimeError("CLERK_SECRET_KEY is not set")
    response = httpx.get(
        f"https://api.clerk.com/v1/users/{user_id}",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()
    emails: list[str] = []
    primary_id = data.get("primary_email_address_id")
    for item in data.get("email_addresses") or []:
        address = (item.get("email_address") or "").lower()
        if item.get("id") == primary_id:
            emails.insert(0, address)
        else:
            emails.append(address)
    email = next((e for e in emails if e), "")
    _email_cache[user_id] = (now + 60, email)
    return email
