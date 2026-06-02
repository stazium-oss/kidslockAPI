"""
Simple JWT-based auth for KidLock web panel.
Two roles: 'parent' (full access) and 'child' (read-only).
"""

import os
import json
import time
import hmac
import hashlib
import base64
from pathlib import Path
from typing import Optional

SECRETS_FILE = Path(__file__).parent / "secrets.json"

# Default credentials (overridden by secrets.json)
DEFAULT_SECRETS = {
    "parent_password": "changeme123",
    "jwt_secret":      "change-this-secret-key-in-production",
}


def _load_secrets() -> dict:
    if SECRETS_FILE.exists():
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    # First run: create defaults file
    SECRETS_FILE.write_text(json.dumps(DEFAULT_SECRETS, indent=2), encoding="utf-8")
    return DEFAULT_SECRETS


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64url_decode(s: str) -> bytes:
    pad = 4 - len(s) % 4
    return base64.urlsafe_b64decode(s + "=" * (pad % 4))


def create_token(role: str, expires_in: int = 86400) -> str:
    """Create a JWT token for the given role (valid for 24h by default)."""
    secrets = _load_secrets()
    header  = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "role": role,
        "iat":  int(time.time()),
        "exp":  int(time.time()) + expires_in,
    }).encode())
    sig = _b64url(
        hmac.new(
            secrets["jwt_secret"].encode(),
            f"{header}.{payload}".encode(),
            hashlib.sha256,
        ).digest()
    )
    return f"{header}.{payload}.{sig}"


def verify_token(token: str) -> Optional[dict]:
    """Verify JWT and return payload dict, or None if invalid/expired."""
    try:
        secrets = _load_secrets()
        header, payload, sig = token.split(".")
        expected = _b64url(
            hmac.new(
                secrets["jwt_secret"].encode(),
                f"{header}.{payload}".encode(),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(_b64url_decode(payload))
        if data["exp"] < time.time():
            return None
        return data
    except Exception:
        return None


def check_parent_password(password: str) -> bool:
    secrets = _load_secrets()
    return hmac.compare_digest(password, secrets["parent_password"])
