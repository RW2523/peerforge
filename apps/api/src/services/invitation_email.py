"""
Invitation delivery
===================
Sends the invite link by email when a transport is configured, and reports
honestly when one is not.

Two transports, tried in order:
  1. SMTP        — set SMTP_HOST (plus user/password if the server needs them)
  2. Supabase    — set SUPABASE_SERVICE_ROLE_KEY; uses the auth admin invite,
                   which also creates the Supabase user

With neither configured the invitation is still created and its token
returned, so the flow works in development — the caller just delivers the
link themselves.
"""
from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Optional, Tuple

import httpx

from ..config import settings


def _invite_url(token: str) -> str:
    base = (settings.app_base_url or "").rstrip("/")
    return f"{base}/invite/{token}"


def _body(org_name: str, role: str, url: str, inviter: Optional[str]) -> Tuple[str, str]:
    who = f"{inviter} has invited you" if inviter else "You have been invited"
    subject = f"{who[:60]} to join {org_name} on PeerForge"
    text = (
        f"{who} to join {org_name} on PeerForge as a {role}.\n\n"
        f"Accept the invitation:\n{url}\n\n"
        f"The link expires in {settings.invite_ttl_days} days. "
        f"If you were not expecting this, you can ignore this message."
    )
    return subject, text


def send_invitation(
    email: str,
    org_name: str,
    role: str,
    token: str,
    inviter: Optional[str] = None,
) -> dict:
    """
    Deliver an invitation.

    Returns {"delivered": bool, "transport": str, "detail": str}. Never raises:
    a delivery failure must not roll back an invitation that was already
    written, or the token would exist with no way to reach it.
    """
    url = _invite_url(token)
    subject, text = _body(org_name, role, url, inviter)

    if settings.smtp_host:
        try:
            _send_smtp(email, subject, text)
            return {"delivered": True, "transport": "smtp", "detail": "sent"}
        except Exception as exc:
            return {"delivered": False, "transport": "smtp", "detail": str(exc)}

    if settings.supabase_service_role_key and settings.supabase_url:
        try:
            _send_supabase(email, url)
            return {"delivered": True, "transport": "supabase", "detail": "sent"}
        except Exception as exc:
            return {"delivered": False, "transport": "supabase", "detail": str(exc)}

    return {
        "delivered": False,
        "transport": "none",
        "detail": "No email transport configured — share the invite link yourself.",
    }


def _send_smtp(to_email: str, subject: str, text: str) -> None:
    message = EmailMessage()
    message["From"] = settings.smtp_from or settings.smtp_user or "no-reply@peerforge.local"
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text)

    cls = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with cls(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if not settings.smtp_use_ssl and settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def _send_supabase(to_email: str, redirect_to: str) -> None:
    """Supabase auth admin invite; creates the user and mails them the link."""
    response = httpx.post(
        f"{settings.supabase_url.rstrip('/')}/auth/v1/invite",
        headers={
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
        },
        json={"email": to_email, "data": {"redirect_to": redirect_to}},
        timeout=15,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Supabase invite failed ({response.status_code}): {response.text[:200]}")
