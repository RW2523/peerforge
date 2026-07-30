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


def _seats_used(cursor, org_id: str) -> int:
    """Counted live rather than stored, so the number cannot drift."""
    cursor.execute(
        "SELECT COUNT(*) AS n FROM organization_members WHERE org_id = %s", (org_id,)
    )
    return cursor.fetchone()["n"]


def _assert_seat_available(cursor, org_id: str) -> None:
    cursor.execute(
        "SELECT seats_purchased FROM organization_seats WHERE org_id = %s", (org_id,)
    )
    row = cursor.fetchone()
    if not row:
        return  # No seat record yet — treat as unmetered (trial).
    purchased = row["seats_purchased"]
    if purchased and _seats_used(cursor, org_id) >= purchased:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"All {purchased} seats are in use. Free a seat or purchase more.",
        )


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
        cursor.execute(
            """INSERT INTO organization_members (org_id, user_id, org_role)
               VALUES (%s, %s, 'org_admin')""",
            (org_id, user_id),
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
            """SELECT user_id, org_role, created_at
               FROM organization_members
               WHERE org_id = %s
               ORDER BY created_at ASC""",
            (org_id,),
        )
        members = [
            {
                "user_id": str(r["user_id"]),
                "role": r["org_role"],
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
        result = redeem_invitation(cursor, token, user_id)
        conn.commit()

    return result


# ── Redemption, shared with first-login provisioning ────────────────────────

def redeem_invitation(cursor, token: str, user_id: str) -> Dict[str, Any]:
    """
    Consume an invitation for `user_id`.

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
    _assert_seat_available(cursor, org_id)

    cursor.execute(
        """INSERT INTO organization_members (org_id, user_id, org_role)
           VALUES (%s, %s, %s)
           ON CONFLICT (org_id, user_id) DO UPDATE SET org_role = EXCLUDED.org_role,
                                                       updated_at = NOW()""",
        (org_id, user_id, invite["invited_role"]),
    )

    workspace_id = str(invite["workspace_id"]) if invite["workspace_id"] else None
    if workspace_id:
        cursor.execute(
            """INSERT INTO user_workspaces (user_id, workspace_id, role)
               VALUES (%s, %s, %s)
               ON CONFLICT (user_id, workspace_id) DO UPDATE SET role = EXCLUDED.role""",
            (user_id, workspace_id, invite["invited_role"]),
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

    purchased = row["seats_purchased"] if row else 0
    return {
        "org_id": org_id,
        "plan": row["plan"] if row else "trial",
        "seats_purchased": purchased,
        "seats_used": used,
        "seats_available": max(0, purchased - used) if purchased else None,
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
