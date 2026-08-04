"""
Organizations, courses, invitations and seats
=============================================
The institutional hierarchy:

    organization (university)  ->  workspace (course/cohort)  ->  member

`tenants` is the organization table — it already carried name, slug, status and
settings, and workspaces already referenced it.

Roles
  org_admin  buy and allocate seats, invite professors, see everything
  professor  create courses, invite students, see every session in their org
  ta         same as professor minus invitations and seat management
  student    their own sessions only
"""
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from ..auth import (
    ELEVATED_ORG_ROLES,
    get_current_user,
    org_role_in,
    require_org_role,
)
from ..config import settings
from ..database import get_db_connection, get_cursor
from ..services.invitation_email import send_invitation

router = APIRouter(tags=["organizations"])

INVITE_TTL_DAYS = settings.invite_ttl_days
ROLES = ("org_admin", "professor", "ta", "student")


# ── Schemas ─────────────────────────────────────────────────────────────────

class CreateOrganizationRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    slug: Optional[str] = Field(None, max_length=100)


class CreateCourseRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field("student")
    # Enrol straight into a course; omit for an organization-level invite.
    workspace_id: Optional[str] = None


class BulkInviteRequest(BaseModel):
    # Accepts a pasted roster: newlines, commas or semicolons.
    emails: str = Field(..., min_length=3, max_length=20000)
    role: str = Field("student")
    workspace_id: Optional[str] = None


class UpdateMemberRoleRequest(BaseModel):
    role: str


class UpdateSeatsRequest(BaseModel):
    seats_purchased: int = Field(..., ge=0)
    plan: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _slugify(name: str) -> str:
    base = "".join(c.lower() if c.isalnum() else "-" for c in name).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    return (base or "org")[:80]


# Which roles consume a purchased seat. Education software is normally priced
# per student, with teaching staff included — counting a professor against a
# student allocation means an institution pays to employ its own faculty.
# This is a pricing decision as much as a technical one; change it here.
BILLABLE_ROLES = ("student",)

# Organization roles and course roles are separate vocabularies, and
# user_workspaces.role has a CHECK constraint that does not include
# 'org_admin'. Writing one straight into the other raised a bare 500 when an
# admin invited a co-admin into a course.
_ORG_TO_WORKSPACE_ROLE = {
    "org_admin": "admin",
    "professor": "professor",
    "ta": "ta",
    "student": "student",
}


def _workspace_role_for(org_role: str) -> str:
    """The course-level role an organization role carries into a workspace."""
    return _ORG_TO_WORKSPACE_ROLE.get(org_role, "student")


def _seats_used(cursor, org_id: str) -> int:
    """Billable members, counted live so the number cannot drift."""
    cursor.execute(
        """SELECT COUNT(*) AS n FROM organization_members
           WHERE org_id = %s AND org_role = ANY(%s)""",
        (org_id, list(BILLABLE_ROLES)),
    )
    return cursor.fetchone()["n"]


def _seats_pending(cursor, org_id: str) -> int:
    """
    Billable invitations that are still live.

    A pending invitation is a seat already promised. Leaving these uncounted
    let an admin send fifty invitations against one free seat, and the refusal
    then surfaced to a student at accept time rather than to the admin who
    caused it. Addresses already on the roster do not double-count.
    """
    cursor.execute(
        """SELECT COUNT(DISTINCT LOWER(i.email)) AS n
           FROM invitations i
           WHERE i.org_id = %s
             AND i.invited_role = ANY(%s)
             AND i.accepted_at IS NULL
             AND i.revoked_at IS NULL
             AND i.expires_at > NOW()
             AND NOT EXISTS (
                 SELECT 1 FROM organization_members om
                 WHERE om.org_id = i.org_id
                   AND LOWER(om.email) = LOWER(i.email)
             )""",
        (org_id, list(BILLABLE_ROLES)),
    )
    return cursor.fetchone()["n"]


def _seat_breakdown(cursor, org_id: str) -> Dict[str, int]:
    """Members per role, so an admin can see what is and is not billed."""
    cursor.execute(
        """SELECT org_role, COUNT(*) AS n FROM organization_members
           WHERE org_id = %s GROUP BY org_role""",
        (org_id,),
    )
    return {r["org_role"]: r["n"] for r in cursor.fetchall()}


def _assert_seat_available(cursor, org_id: str, count_pending: bool = True) -> None:
    """
    Refuse when the organization has no seat left to commit.

    `count_pending` includes invitations that have been sent but not yet
    accepted. That is right when issuing a new invitation and wrong when
    redeeming one, since the invitation being redeemed already holds its own
    reservation and would otherwise block itself.
    """
    cursor.execute(
        "SELECT seats_purchased FROM organization_seats WHERE org_id = %s", (org_id,)
    )
    row = cursor.fetchone()
    if not row:
        return  # No seat record yet — treat as unmetered (trial).
    purchased = row["seats_purchased"]
    if not purchased:
        return

    used = _seats_used(cursor, org_id)
    committed = used + (_seats_pending(cursor, org_id) if count_pending else 0)
    if committed < purchased:
        return

    outstanding = committed - used
    detail = f"All {purchased} seats are committed"
    if outstanding:
        detail += f" ({used} in use, {outstanding} awaiting acceptance)"
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail + ". Free a seat, revoke an invitation, or purchase more.",
    )


def _name_from_email(email: Optional[str]) -> Optional[str]:
    """A readable stand-in until the person sets a real name."""
    if not email or "@" not in email:
        return None
    local = email.split("@", 1)[0]
    return " ".join(part.capitalize() for part in local.replace(".", " ").replace("_", " ").split())


def _parse_email_list(raw: str) -> List[str]:
    """Split a pasted roster and keep plausible addresses, de-duplicated."""
    import re

    parts = re.split(r"[\s,;]+", raw or "")
    seen, out = set(), []
    for part in parts:
        candidate = part.strip().strip("<>").lower()
        # Deliberately permissive: the goal is to skip obvious junk in a paste,
        # not to re-implement address validation.
        if "@" not in candidate or "." not in candidate.split("@")[-1]:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out[:500]


def _validate_role(role: str) -> str:
    if role not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown role '{role}'. Expected one of: {', '.join(ROLES)}",
        )
    return role


# ── Organizations ───────────────────────────────────────────────────────────

@router.post("/organizations", status_code=status.HTTP_201_CREATED)
async def create_organization(
    request: CreateOrganizationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a university. The creator becomes its first org_admin."""
    user_id = current_user.get("user_id")
    org_id = str(uuid.uuid4())
    slug = _slugify(request.slug or request.name)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("SELECT 1 FROM tenants WHERE slug = %s", (slug,))
        if cursor.fetchone():
            slug = f"{slug}-{org_id[:6]}"

        cursor.execute(
            "INSERT INTO tenants (tenant_id, name, slug) VALUES (%s, %s, %s)",
            (org_id, request.name, slug),
        )
        founder_email = current_user.get("email")
        cursor.execute(
            """INSERT INTO organization_members (org_id, user_id, org_role, email, display_name)
               VALUES (%s, %s, 'org_admin', %s, %s)""",
            (org_id, user_id, founder_email, _name_from_email(founder_email)),
        )
        cursor.execute(
            "INSERT INTO organization_seats (org_id, plan) VALUES (%s, 'trial')",
            (org_id,),
        )
        conn.commit()

    return {"org_id": org_id, "name": request.name, "slug": slug, "your_role": "org_admin"}


@router.get("/me/organizations")
async def my_organizations(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Organizations the caller belongs to."""
    return {"organizations": current_user.get("organizations") or []}


@router.get("/organizations/{org_id}/members")
async def list_members(
    org_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """The roster. Any member may see who else is in their organization."""
    require_org_role(current_user, org_id)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """SELECT user_id, org_role, email, display_name, created_at
               FROM organization_members
               WHERE org_id = %s
               ORDER BY created_at ASC""",
            (org_id,),
        )
        members = [
            {
                "user_id": str(r["user_id"]),
                "role": r["org_role"],
                "email": r["email"],
                "display_name": r["display_name"] or _name_from_email(r["email"]),
                "joined_at": r["created_at"].isoformat(),
            }
            for r in cursor.fetchall()
        ]

    return {"org_id": org_id, "members": members, "count": len(members)}


@router.patch("/organizations/{org_id}/members/{user_id}")
async def update_member_role(
    org_id: str,
    user_id: str,
    request: UpdateMemberRoleRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Change someone's role. Admins only."""
    require_org_role(current_user, org_id, "org_admin")
    new_role = _validate_role(request.role)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)

        # Removing the last admin would leave the organization unmanageable.
        if new_role != "org_admin":
            cursor.execute(
                """SELECT COUNT(*) AS n FROM organization_members
                   WHERE org_id = %s AND org_role = 'org_admin' AND user_id <> %s""",
                (org_id, user_id),
            )
            if cursor.fetchone()["n"] == 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="This is the last admin — promote someone else first.",
                )

        cursor.execute(
            """UPDATE organization_members
               SET org_role = %s, updated_at = NOW()
               WHERE org_id = %s AND user_id = %s
               RETURNING org_role""",
            (new_role, org_id, user_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Member not found")

        # A professor demoted to student keeps professor powers inside every
        # course until this row follows: workspace role is read from here,
        # not from the organization membership.
        cursor.execute(
            """UPDATE user_workspaces SET role = %s
               WHERE user_id = %s
                 AND workspace_id IN (
                     SELECT workspace_id FROM workspaces WHERE tenant_id = %s
                 )""",
            (_workspace_role_for(new_role), user_id, org_id),
        )
        conn.commit()

    return {"org_id": org_id, "user_id": user_id, "role": row["org_role"]}


@router.delete("/organizations/{org_id}/members/{user_id}")
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Remove someone from the organization, freeing their seat."""
    require_org_role(current_user, org_id, "org_admin")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """SELECT COUNT(*) AS n FROM organization_members
               WHERE org_id = %s AND org_role = 'org_admin' AND user_id <> %s""",
            (org_id, user_id),
        )
        if cursor.fetchone()["n"] == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This is the last admin — promote someone else first.",
            )

        cursor.execute(
            "DELETE FROM organization_members WHERE org_id = %s AND user_id = %s",
            (org_id, user_id),
        )
        removed = cursor.rowcount

        # Course membership lives in a second table. Dropping only the
        # organization row frees the seat while leaving the person full
        # access to every course in it - billed to nobody, visible to all.
        cursor.execute(
            """DELETE FROM user_workspaces
               WHERE user_id = %s
                 AND workspace_id IN (
                     SELECT workspace_id FROM workspaces WHERE tenant_id = %s
                 )""",
            (user_id, org_id),
        )
        conn.commit()

    if not removed:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"removed": True, "org_id": org_id, "user_id": user_id}


# ── Courses ─────────────────────────────────────────────────────────────────

@router.post("/organizations/{org_id}/courses", status_code=status.HTTP_201_CREATED)
async def create_course(
    org_id: str,
    request: CreateCourseRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Create a course space. The creator is enrolled as its professor."""
    require_org_role(current_user, org_id, "org_admin", "professor")
    user_id = current_user.get("user_id")
    workspace_id = str(uuid.uuid4())
    slug = f"{_slugify(request.name)}-{workspace_id[:6]}"

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """INSERT INTO workspaces (workspace_id, tenant_id, name, slug, description)
               VALUES (%s, %s, %s, %s, %s)""",
            (workspace_id, org_id, request.name, slug, request.description),
        )
        cursor.execute(
            """INSERT INTO user_workspaces (user_id, workspace_id, role)
               VALUES (%s, %s, 'professor')
               ON CONFLICT (user_id, workspace_id) DO NOTHING""",
            (user_id, workspace_id),
        )
        conn.commit()

    return {
        "workspace_id": workspace_id,
        "org_id": org_id,
        "name": request.name,
        "slug": slug,
        "your_role": "professor",
    }


@router.get("/organizations/{org_id}/courses")
async def list_courses(
    org_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Courses in the organization. Students see only the ones they're in."""
    role = require_org_role(current_user, org_id)
    user_id = current_user.get("user_id")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        if role in ELEVATED_ORG_ROLES:
            cursor.execute(
                """SELECT workspace_id, name, slug, description, created_at
                   FROM workspaces WHERE tenant_id = %s ORDER BY created_at DESC""",
                (org_id,),
            )
        else:
            cursor.execute(
                """SELECT w.workspace_id, w.name, w.slug, w.description, w.created_at
                   FROM workspaces w
                   JOIN user_workspaces uw ON uw.workspace_id = w.workspace_id
                   WHERE w.tenant_id = %s AND uw.user_id = %s
                   ORDER BY w.created_at DESC""",
                (org_id, user_id),
            )
        courses = [
            {
                "workspace_id": str(r["workspace_id"]),
                "name": r["name"],
                "slug": r["slug"],
                "description": r["description"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in cursor.fetchall()
        ]

    return {"org_id": org_id, "courses": courses}


# ── Invitations ─────────────────────────────────────────────────────────────

@router.post("/organizations/{org_id}/invitations", status_code=status.HTTP_201_CREATED)
async def create_invitation(
    org_id: str,
    request: CreateInvitationRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Invite someone by email.

    Returns the token so the caller can deliver the link. There is no mail
    sender wired up yet, so delivery is the caller's responsibility — see
    the Phase 1 notes.
    """
    actor_role = require_org_role(current_user, org_id, "org_admin", "professor")
    invited_role = _validate_role(request.role)

    # A professor may staff their courses but not mint administrators.
    if actor_role == "professor" and invited_role in ("org_admin", "professor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an org_admin can invite professors or administrators",
        )

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        _assert_seat_available(cursor, org_id)

        if request.workspace_id:
            cursor.execute(
                "SELECT 1 FROM workspaces WHERE workspace_id = %s AND tenant_id = %s",
                (request.workspace_id, org_id),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404, detail="That course is not in this organization"
                )

        cursor.execute(
            """INSERT INTO invitations
                   (org_id, workspace_id, email, invited_role, token, invited_by, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING invite_id, created_at""",
            (org_id, request.workspace_id, request.email.lower(), invited_role,
             token, current_user.get("user_id"), expires_at),
        )
        row = cursor.fetchone()

        cursor.execute("SELECT name FROM tenants WHERE tenant_id = %s", (org_id,))
        org_name = (cursor.fetchone() or {}).get("name") or "your institution"
        conn.commit()

    # Delivery happens after the commit: a mail failure must not discard an
    # invitation that already exists, or the token would be unreachable.
    delivery = send_invitation(
        email=request.email,
        org_name=org_name,
        role=invited_role,
        token=token,
        inviter=current_user.get("email"),
    )

    return {
        "invite_id": str(row["invite_id"]),
        "email": request.email,
        "role": invited_role,
        "workspace_id": request.workspace_id,
        # Returned so the inviter can share the link when no mail transport is
        # configured, or when delivery failed.
        "token": token,
        "invite_url": f"{settings.app_base_url.rstrip('/')}/invite/{token}",
        "expires_at": expires_at.isoformat(),
        "email_delivered": delivery["delivered"],
        "delivery": delivery,
    }


@router.get("/organizations/{org_id}/invitations")
async def list_invitations(
    org_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Outstanding and historical invitations."""
    require_org_role(current_user, org_id, "org_admin", "professor")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """SELECT invite_id, email, invited_role, workspace_id,
                      expires_at, accepted_at, revoked_at, created_at
               FROM invitations WHERE org_id = %s ORDER BY created_at DESC""",
            (org_id,),
        )
        rows = cursor.fetchall()

    now = datetime.now(timezone.utc)

    def _state(r):
        if r["revoked_at"]:
            return "revoked"
        if r["accepted_at"]:
            return "accepted"
        if r["expires_at"] <= now:
            return "expired"
        return "pending"

    return {
        "org_id": org_id,
        "invitations": [
            {
                "invite_id": str(r["invite_id"]),
                "email": r["email"],
                "role": r["invited_role"],
                "workspace_id": str(r["workspace_id"]) if r["workspace_id"] else None,
                "state": _state(r),
                "expires_at": r["expires_at"].isoformat(),
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/organizations/{org_id}/invitations/bulk", status_code=status.HTTP_201_CREATED)
async def create_invitations_bulk(
    org_id: str,
    request: BulkInviteRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Invite a whole class at once.

    Reports an outcome per address rather than failing the batch: one bad
    address in a pasted roster of forty should not discard the other
    thirty-nine.
    """
    actor_role = require_org_role(current_user, org_id, "org_admin", "professor")
    invited_role = _validate_role(request.role)

    if actor_role == "professor" and invited_role in ("org_admin", "professor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an org_admin can invite professors or administrators",
        )

    addresses = _parse_email_list(request.emails)
    if not addresses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email addresses found in that list",
        )

    results = []
    with get_db_connection() as conn:
        cursor = get_cursor(conn)

        if request.workspace_id:
            cursor.execute(
                "SELECT 1 FROM workspaces WHERE workspace_id = %s AND tenant_id = %s",
                (request.workspace_id, org_id),
            )
            if not cursor.fetchone():
                raise HTTPException(
                    status_code=404, detail="That course is not in this organization"
                )

        cursor.execute("SELECT name FROM tenants WHERE tenant_id = %s", (org_id,))
        org_name = (cursor.fetchone() or {}).get("name") or "your institution"

        for email in addresses:
            try:
                _assert_seat_available(cursor, org_id)
            except HTTPException as exc:
                # Seats ran out partway through; the rest are reported as
                # skipped rather than silently dropped.
                results.append({"email": email, "state": "skipped", "detail": exc.detail})
                continue

            cursor.execute(
                """SELECT 1 FROM organization_members om
                   WHERE om.org_id = %s AND LOWER(om.email) = LOWER(%s)""",
                (org_id, email),
            )
            if cursor.fetchone():
                results.append({"email": email, "state": "already_member", "detail": None})
                continue

            cursor.execute(
                """SELECT 1 FROM invitations
                   WHERE org_id = %s AND LOWER(email) = LOWER(%s)
                     AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > NOW()""",
                (org_id, email),
            )
            if cursor.fetchone():
                results.append({"email": email, "state": "already_invited", "detail": None})
                continue

            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS)
            cursor.execute(
                """INSERT INTO invitations
                       (org_id, workspace_id, email, invited_role, token, invited_by, expires_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (org_id, request.workspace_id, email, invited_role, token,
                 current_user.get("user_id"), expires_at),
            )
            results.append({
                "email": email,
                "state": "invited",
                "invite_url": f"{settings.app_base_url.rstrip('/')}/invite/{token}",
                "token": token,
                "detail": None,
            })

        conn.commit()

    # Delivery after commit, as for single invites.
    delivered = 0
    for entry in results:
        if entry["state"] != "invited":
            continue
        outcome = send_invitation(
            email=entry["email"], org_name=org_name, role=invited_role,
            token=entry["token"], inviter=current_user.get("email"),
        )
        entry["email_delivered"] = outcome["delivered"]
        delivered += 1 if outcome["delivered"] else 0

    counts: Dict[str, int] = {}
    for entry in results:
        counts[entry["state"]] = counts.get(entry["state"], 0) + 1

    return {
        "org_id": org_id,
        "submitted": len(addresses),
        "counts": counts,
        "emails_delivered": delivered,
        "results": results,
    }


@router.delete("/organizations/{org_id}/invitations/{invite_id}")
async def revoke_invitation(
    org_id: str,
    invite_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Revoke an invitation that hasn't been accepted."""
    require_org_role(current_user, org_id, "org_admin", "professor")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """UPDATE invitations SET revoked_at = NOW()
               WHERE invite_id = %s AND org_id = %s AND accepted_at IS NULL
               RETURNING invite_id""",
            (invite_id, org_id),
        )
        row = cursor.fetchone()
        conn.commit()

    if not row:
        raise HTTPException(
            status_code=404, detail="No pending invitation with that id"
        )
    return {"revoked": True, "invite_id": invite_id}


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Accept an invitation, joining the organization and any named course."""
    user_id = current_user.get("user_id")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        result = redeem_invitation(
            cursor, token, user_id, caller_email=current_user.get("email")
        )
        conn.commit()

    return result


# ── Redemption, shared with first-login provisioning ────────────────────────

def _assert_invited_party(invited_email: Optional[str], caller_email: Optional[str]) -> None:
    """
    Confirm the caller is the person the invitation was addressed to.

    An invitation is an offer to one address, not a bearer credential. Without
    this, anyone who comes by the token - a forwarded email, a shared screen,
    a proxy log, a browser history - is handed the invited role, and
    invited_role may be org_admin.
    """
    if not settings.require_auth:
        # Local dev authenticates nobody, so there is no identity to bind to.
        return
    if not caller_email:
        raise HTTPException(
            status_code=403,
            detail="Your account has no verified email address, so this "
                   "invitation cannot be matched to you.",
        )
    if caller_email.strip().lower() != (invited_email or "").strip().lower():
        raise HTTPException(
            status_code=403,
            detail="This invitation was issued to a different email address.",
        )


def redeem_invitation(cursor, token: str, user_id: str,
                      display_name: Optional[str] = None,
                      caller_email: Optional[str] = None) -> Dict[str, Any]:
    """
    Consume an invitation for `user_id`, who must be its addressee.

    Lives here rather than in the route so first login can redeem a pending
    invitation instead of provisioning an orphan personal workspace.
    """
    cursor.execute(
        """SELECT invite_id, org_id, workspace_id, email, invited_role,
                  expires_at, accepted_at, accepted_by, revoked_at
           FROM invitations WHERE token = %s
           FOR UPDATE""",
        (token,),
    )
    invite = cursor.fetchone()

    if not invite:
        raise HTTPException(status_code=404, detail="Invitation not found")
    # Ahead of the revoked/expired branches: a stranger holding the token
    # should not learn anything about it, not even that it is spent.
    _assert_invited_party(invite["email"], caller_email)
    if invite["revoked_at"]:
        raise HTTPException(status_code=410, detail="This invitation was revoked")
    if invite["accepted_at"]:
        # Signing in already redeems a pending invitation for your address, so
        # by the time you follow the emailed link it may be spent - by you.
        # Re-accepting your own invitation is a no-op, not a conflict.
        if str(invite["accepted_by"]) == str(user_id):
            return {
                "org_id": str(invite["org_id"]),
                "workspace_id": str(invite["workspace_id"]) if invite["workspace_id"] else None,
                "role": invite["invited_role"],
                "accepted": True,
                "already_accepted": True,
            }
        raise HTTPException(status_code=409, detail="This invitation was already used")
    if invite["expires_at"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="This invitation has expired")

    org_id = str(invite["org_id"])
    # count_pending=False: this invitation already holds a reservation, and
    # counting it here would make every invitation block its own redemption.
    _assert_seat_available(cursor, org_id, count_pending=False)

    # Redeeming an invitation rewrites org_role, which is a role change by
    # another name - and it was the one path that skipped the last-admin guard
    # that PATCH and DELETE enforce. A professor may invite students, so
    # inviting the sole administrator's address as 'student' left the
    # organization with nobody able to administer it.
    cursor.execute(
        "SELECT org_role FROM organization_members WHERE org_id = %s AND user_id = %s",
        (org_id, user_id),
    )
    existing = cursor.fetchone()
    if (existing and existing["org_role"] == "org_admin"
            and invite["invited_role"] != "org_admin"):
        cursor.execute(
            """SELECT COUNT(*) AS n FROM organization_members
               WHERE org_id = %s AND org_role = 'org_admin' AND user_id <> %s""",
            (org_id, user_id),
        )
        if cursor.fetchone()["n"] == 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Accepting this would remove the last administrator. "
                       "Promote someone else first.",
            )

    # The invitation address is the only identity we reliably have: the API
    # has no view onto auth.users, which may belong to another app.
    cursor.execute(
        """INSERT INTO organization_members (org_id, user_id, org_role, email, display_name)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (org_id, user_id) DO UPDATE
               SET org_role = EXCLUDED.org_role,
                   email = COALESCE(organization_members.email, EXCLUDED.email),
                   display_name = COALESCE(organization_members.display_name,
                                           EXCLUDED.display_name),
                   updated_at = NOW()""",
        (org_id, user_id, invite["invited_role"], invite["email"],
         display_name or _name_from_email(invite["email"])),
    )

    workspace_id = str(invite["workspace_id"]) if invite["workspace_id"] else None
    if workspace_id:
        cursor.execute(
            """INSERT INTO user_workspaces (user_id, workspace_id, role)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, workspace_id) DO UPDATE SET role = EXCLUDED.role""",
            (user_id, workspace_id, _workspace_role_for(invite["invited_role"])),
        )

    cursor.execute(
        """UPDATE invitations SET accepted_at = NOW(), accepted_by = %s
           WHERE invite_id = %s""",
        (user_id, invite["invite_id"]),
    )

    return {
        "org_id": org_id,
        "workspace_id": workspace_id,
        "role": invite["invited_role"],
        "accepted": True,
    }


# ── Cohort ──────────────────────────────────────────────────────────────────

@router.get("/organizations/{org_id}/cohort")
async def cohort_overview(
    org_id: str,
    workspace_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Who is progressing and who has not started.

    Scoped to one course when workspace_id is given, otherwise the whole
    organization. Members with no sessions are included deliberately — the
    students who have done nothing are the ones a professor most needs to see,
    and an activity-driven query would omit exactly them.
    """
    require_org_role(current_user, org_id, "org_admin", "professor", "ta")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)

        if workspace_id:
            cursor.execute(
                "SELECT name FROM workspaces WHERE workspace_id = %s AND tenant_id = %s",
                (workspace_id, org_id),
            )
            course = cursor.fetchone()
            if not course:
                raise HTTPException(
                    status_code=404, detail="That course is not in this organization"
                )

        cursor.execute(
            """
            WITH scoped_debates AS (
                SELECT d.debate_id, d.owner_user_id, d.state, d.created_at
                FROM debates d
                JOIN workspaces w ON w.workspace_id = d.workspace_id
                WHERE w.tenant_id = %(org_id)s
                  AND (%(workspace_id)s::uuid IS NULL OR d.workspace_id = %(workspace_id)s::uuid)
            ),
            latest_assessment AS (
                SELECT DISTINCT ON (a.debate_id)
                       a.debate_id, a.overall_score, a.generated_at
                FROM academic_assessments a
                JOIN scoped_debates sd ON sd.debate_id = a.debate_id
                ORDER BY a.debate_id, a.generated_at DESC
            ),
            first_assessment AS (
                SELECT DISTINCT ON (a.debate_id)
                       a.debate_id, a.overall_score
                FROM academic_assessments a
                JOIN scoped_debates sd ON sd.debate_id = a.debate_id
                ORDER BY a.debate_id, a.generated_at ASC
            )
            SELECT om.user_id,
                   om.org_role,
                   om.email,
                   om.display_name,
                   COUNT(sd.debate_id)                                   AS sessions,
                   COUNT(*) FILTER (WHERE sd.state = 'ended')            AS sessions_completed,
                   MAX(sd.created_at)                                    AS last_activity,
                   AVG(la.overall_score)                                 AS latest_score,
                   AVG(la.overall_score - fa.overall_score)              AS score_delta
            FROM organization_members om
            LEFT JOIN scoped_debates sd     ON sd.owner_user_id = om.user_id
            LEFT JOIN latest_assessment la  ON la.debate_id = sd.debate_id
            LEFT JOIN first_assessment fa   ON fa.debate_id = sd.debate_id
            WHERE om.org_id = %(org_id)s
              -- Scoped to the course when one is named. Filtering only the
              -- debates and invitations, as this did, still listed every
              -- person in the university under each individual course.
              AND (
                %(workspace_id)s::uuid IS NULL
                OR EXISTS (
                    SELECT 1 FROM user_workspaces uw
                    WHERE uw.user_id = om.user_id
                      AND uw.workspace_id = %(workspace_id)s::uuid
                )
              )
            GROUP BY om.user_id, om.org_role, om.email, om.display_name
            ORDER BY COUNT(sd.debate_id) DESC, om.email NULLS LAST
            """,
            {"org_id": org_id, "workspace_id": workspace_id},
        )
        rows = cursor.fetchall()

    people = []
    for r in rows:
        sessions = int(r["sessions"] or 0)
        people.append({
            "user_id": str(r["user_id"]),
            "role": r["org_role"],
            "email": r["email"],
            "display_name": r["display_name"] or _name_from_email(r["email"]),
            "sessions": sessions,
            "sessions_completed": int(r["sessions_completed"] or 0),
            "last_activity": r["last_activity"].isoformat() if r["last_activity"] else None,
            "latest_score": round(float(r["latest_score"]), 1) if r["latest_score"] is not None else None,
            "score_delta": round(float(r["score_delta"]), 1) if r["score_delta"] is not None else None,
            "not_started": sessions == 0,
        })

    # Someone invited who never signed in is the professor's most important
    # row and has no membership record at all, so they would otherwise be
    # invisible in exactly the view meant to surface them.
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """SELECT email, invited_role, created_at, expires_at
               FROM invitations
               WHERE org_id = %(org_id)s
                 AND accepted_at IS NULL
                 AND revoked_at IS NULL
                 AND (%(workspace_id)s::uuid IS NULL OR workspace_id = %(workspace_id)s::uuid)
               ORDER BY created_at DESC""",
            {"org_id": org_id, "workspace_id": workspace_id},
        )
        now = datetime.now(timezone.utc)
        for r in cursor.fetchall():
            people.append({
                "user_id": None,
                "role": r["invited_role"],
                "email": r["email"],
                "display_name": _name_from_email(r["email"]),
                "sessions": 0,
                "sessions_completed": 0,
                "last_activity": None,
                "latest_score": None,
                "score_delta": None,
                "not_started": True,
                "invited_at": r["created_at"].isoformat(),
                "invite_state": "expired" if r["expires_at"] <= now else "pending",
            })

    students = [p for p in people if p["role"] == "student"]
    return {
        "org_id": org_id,
        "workspace_id": workspace_id,
        "people": people,
        "summary": {
            "members": sum(1 for p in people if p["user_id"]),
            "invited_not_joined": sum(1 for p in people if not p["user_id"]),
            "students": len(students),
            "students_not_started": sum(1 for p in students if p["not_started"]),
            "sessions_total": sum(p["sessions"] for p in people),
        },
    }


# ── Seats ───────────────────────────────────────────────────────────────────

@router.get("/organizations/{org_id}/seats")
async def get_seats(
    org_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Seat allocation and live usage."""
    require_org_role(current_user, org_id, "org_admin", "professor")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """SELECT seats_purchased, plan, period_end
               FROM organization_seats WHERE org_id = %s""",
            (org_id,),
        )
        row = cursor.fetchone()
        used = _seats_used(cursor, org_id)
        pending = _seats_pending(cursor, org_id)
        breakdown = _seat_breakdown(cursor, org_id)

    purchased = row["seats_purchased"] if row else 0
    return {
        "org_id": org_id,
        "plan": row["plan"] if row else "trial",
        "seats_purchased": purchased,
        "seats_used": used,
        # Outstanding invitations hold seats too. Reporting only `seats_used`
        # showed capacity that the next invitation would immediately refuse.
        "seats_pending": pending,
        "seats_committed": used + pending,
        "billable_roles": list(BILLABLE_ROLES),
        "members_by_role": breakdown,
        "seats_available": max(0, purchased - used - pending) if purchased else None,
        "period_end": row["period_end"].isoformat() if row and row["period_end"] else None,
    }


@router.put("/organizations/{org_id}/seats")
async def update_seats(
    org_id: str,
    request: UpdateSeatsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Set the seat allocation. Admins only."""
    require_org_role(current_user, org_id, "org_admin")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        used = _seats_used(cursor, org_id)
        if request.seats_purchased and request.seats_purchased < used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{used} seats are already in use — remove members before reducing to {request.seats_purchased}.",
            )
        cursor.execute(
            """INSERT INTO organization_seats (org_id, seats_purchased, plan)
               VALUES (%s, %s, COALESCE(%s, 'trial'))
               ON CONFLICT (org_id) DO UPDATE
                   SET seats_purchased = EXCLUDED.seats_purchased,
                       plan = COALESCE(%s, organization_seats.plan),
                       updated_at = NOW()""",
            (org_id, request.seats_purchased, request.plan, request.plan),
        )
        conn.commit()

    return {"org_id": org_id, "seats_purchased": request.seats_purchased, "seats_used": used}
