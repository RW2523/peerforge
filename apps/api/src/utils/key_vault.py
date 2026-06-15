"""
Key vault — encryption at rest for user-supplied provider API keys.

Keys are encrypted with Fernet (AES-128-CBC + HMAC) using a key derived from
the KEY_ENCRYPTION_SECRET environment variable. The plaintext key is never
returned to the client — only a masked suffix for display.
"""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings


def _fernet() -> Fernet:
    secret = getattr(settings, "key_encryption_secret", "") or ""
    if not secret:
        raise RuntimeError(
            "KEY_ENCRYPTION_SECRET is not configured — refusing to store API keys "
            "without encryption at rest."
        )
    derived = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_key(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_key(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError(
            "Stored key cannot be decrypted (KEY_ENCRYPTION_SECRET changed?)"
        ) from exc


def mask_key(plaintext: str) -> str:
    """Display form: 'sk-or-…f2a4' — never the full key."""
    tail = plaintext[-4:] if len(plaintext) >= 4 else "****"
    return f"sk-or-…{tail}"
