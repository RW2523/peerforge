"""
Certificate signing (Pillar 3 hardening)
========================================
Ed25519 signatures over the certificate's canonical anchor payload — the same
bytes whose sha256 is the tamper-evident anchor. Verification therefore checks
two independent properties:

  * hash integrity  — sha256(canonical payload) == anchor_hash
  * authenticity    — Ed25519 signature over those bytes verifies against the
                      platform public key

Key management: the active keypair lives in ``signing_keys`` for local dev.
Production should provide the private key via CERT_SIGNING_KEY_PEM (preferred
by the loader) so the database never holds it.
"""
from __future__ import annotations

import base64
import hashlib
import os
from typing import Optional, Tuple

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ..database import get_db_connection, get_cursor


def _key_id_for(public_pem: str) -> str:
    return hashlib.sha256(public_pem.encode("utf-8")).hexdigest()[:12]


def _load_env_key() -> Optional[Tuple[str, Ed25519PrivateKey, str]]:
    pem = os.environ.get("CERT_SIGNING_KEY_PEM")
    if not pem:
        return None
    private_key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError("CERT_SIGNING_KEY_PEM must be an Ed25519 private key")
    public_pem = (
        private_key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode("utf-8")
    )
    return _key_id_for(public_pem), private_key, public_pem


def get_active_signing_key() -> Tuple[str, Ed25519PrivateKey, str]:
    """Return (key_id, private_key, public_pem) — env key first, else the DB
    key, generating and persisting one on first use."""
    env = _load_env_key()
    if env:
        return env

    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT key_id, private_key, public_key FROM signing_keys "
            "WHERE active = TRUE ORDER BY created_at DESC LIMIT 1"
        )
        row = cur.fetchone()
        if row:
            private_key = serialization.load_pem_private_key(
                row["private_key"].encode("utf-8"), password=None
            )
            return row["key_id"], private_key, row["public_key"]

        private_key = Ed25519PrivateKey.generate()
        private_pem = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = (
            private_key.public_key()
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode("utf-8")
        )
        key_id = _key_id_for(public_pem)
        cur.execute(
            "INSERT INTO signing_keys (key_id, private_key, public_key) VALUES (%s, %s, %s) "
            "ON CONFLICT (key_id) DO NOTHING",
            (key_id, private_pem, public_pem),
        )
        conn.commit()
        return key_id, private_key, public_pem


def sign_canonical(canonical: str) -> Tuple[str, str, str]:
    """Sign the canonical payload string. Returns (key_id, signature_b64, public_pem)."""
    key_id, private_key, public_pem = get_active_signing_key()
    signature = private_key.sign(canonical.encode("utf-8"))
    return key_id, base64.b64encode(signature).decode("ascii"), public_pem


def verify_signature(public_pem: str, canonical: str, signature_b64: str) -> bool:
    try:
        public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
        if not isinstance(public_key, Ed25519PublicKey):
            return False
        public_key.verify(base64.b64decode(signature_b64), canonical.encode("utf-8"))
        return True
    except Exception:
        return False
