"""
Per-user settings — account-stored OpenRouter key
=================================================
PUT    /me/openrouter-key   → validate, encrypt, store; returns masked form
GET    /me/openrouter-key   → {connected, masked}
DELETE /me/openrouter-key   → remove the stored key

The key is collected during onboarding (skippable) or in Settings, stored
encrypted at rest, and resolved server-side on every request that needs one
(see the key-resolution middleware in main.py). The full key is never sent
back to the browser.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..auth import get_current_user
from ..database import get_db_connection, get_cursor
from ..utils.key_vault import encrypt_key, decrypt_key, mask_key

router = APIRouter(tags=["user-settings"])


class SaveKeyRequest(BaseModel):
    api_key: str


def _user_id(current_user: Dict[str, Any]) -> str:
    return str(current_user.get("user_id") or current_user.get("sub") or "test-user")


# Short-lived cache so the key-resolution middleware doesn't hit the DB on
# every request. Invalidated on save/delete.
import time as _time

_key_cache: Dict[str, Any] = {}
_KEY_CACHE_TTL = 60.0


def get_cached_openrouter_key(user_id: str) -> Optional[str]:
    cached = _key_cache.get(user_id)
    if cached and cached[1] > _time.monotonic():
        return cached[0]
    key = get_stored_openrouter_key(user_id)
    _key_cache[user_id] = (key, _time.monotonic() + _KEY_CACHE_TTL)
    return key


def invalidate_key_cache(user_id: str) -> None:
    _key_cache.pop(user_id, None)


def get_stored_openrouter_key(user_id: str) -> Optional[str]:
    """Decrypt and return the user's stored OpenRouter key, or None."""
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT openrouter_key_encrypted FROM user_settings WHERE user_id = %s",
            (user_id,),
        )
        row = cur.fetchone()
    if not row or not row.get("openrouter_key_encrypted"):
        return None
    try:
        return decrypt_key(row["openrouter_key_encrypted"])
    except ValueError:
        return None


@router.put("/me/openrouter-key")
async def save_openrouter_key(
    request: SaveKeyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    key = request.api_key.strip()
    if not key.startswith("sk-or-"):
        raise HTTPException(
            status_code=400,
            detail="That does not look like an OpenRouter key (expected 'sk-or-…').",
        )

    user_id = _user_id(current_user)
    encrypted = encrypt_key(key)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("""
            INSERT INTO user_settings (user_id, openrouter_key_encrypted, openrouter_key_last4, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE
              SET openrouter_key_encrypted = EXCLUDED.openrouter_key_encrypted,
                  openrouter_key_last4     = EXCLUDED.openrouter_key_last4,
                  updated_at               = NOW()
        """, (user_id, encrypted, key[-4:]))
        conn.commit()

    invalidate_key_cache(user_id)
    return {"connected": True, "masked": mask_key(key)}


@router.get("/me/openrouter-key")
async def get_openrouter_key_status(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = _user_id(current_user)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT openrouter_key_last4 FROM user_settings WHERE user_id = %s AND openrouter_key_encrypted IS NOT NULL",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return {"connected": False, "masked": None}
    return {"connected": True, "masked": f"sk-or-…{row['openrouter_key_last4']}"}


@router.delete("/me/openrouter-key")
async def delete_openrouter_key(
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    user_id = _user_id(current_user)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("DELETE FROM user_settings WHERE user_id = %s", (user_id,))
        conn.commit()
    invalidate_key_cache(user_id)
    return {"connected": False}
