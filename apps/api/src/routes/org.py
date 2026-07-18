"""Departments and workspace invites (institutional layer, B2)
================================================================
Departments group a workspace's review sessions for the advisor console.
Invites let an advisor bring members into the workspace with a role; the role
lands in user_workspaces and is enforced everywhere via require_role().
Both are Institution-plan features (see services/plans.py).
"""
import secrets
import uuid as uuid_lib
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import get_current_user, require_role
from ..database import get_db_connection, get_cursor
from ..services.plans import require_feature

router = APIRouter(tags=["org"])

ASSIGNABLE_ROLES = {"advisor", "student"}


class CreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SetDepartmentRequest(BaseModel):
    department_id: Optional[str] = None


class CreateInviteRequest(BaseModel):
    role: str = "student"
    department_id: Optional[str] = None
    expires_days: int = Field(default=14, ge=1, le=90)


def _check_workspace(workspace_id: str, user: Dict[str, Any]) -> None:
    if workspace_id != user["workspace_id"]:
        raise HTTPException(status_code=403, detail="Access denied to this workspace")


def _validate_uuid(value: str, field: str) -> None:
    """Reject malformed UUIDs with a 400 before they reach a ::uuid cast."""
    try:
        uuid_lib.UUID(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} is not a valid UUID")


@router.get("/workspaces/{workspace_id}/departments")
async def list_departments(
    workspace_id: str,
    _adv: Dict[str, Any] = Depends(require_role("advisor")),
):
    """Departments in this workspace, with how many sessions each holds."""
    _check_workspace(workspace_id, _adv)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT dep.department_id, dep.name, dep.created_at,
                   COUNT(d.debate_id) AS session_count
            FROM departments dep
            LEFT JOIN debates d ON d.department_id = dep.department_id
            WHERE dep.workspace_id = %s
            GROUP BY dep.department_id, dep.name, dep.created_at
            ORDER BY dep.name
            """,
            (workspace_id,),
        )
        rows = cur.fetchall()
    return {
        "workspace_id": workspace_id,
        "departments": [
            {
                "department_id": str(r["department_id"]),
                "name": r["name"],
                "session_count": int(r["session_count"] or 0),
            }
            for r in rows
        ],
    }


@router.post("/workspaces/{workspace_id}/departments")
async def create_department(
    workspace_id: str,
    request: CreateDepartmentRequest,
    _adv: Dict[str, Any] = Depends(require_role("advisor")),
):
    """Create a department (idempotent on name)."""
    _check_workspace(workspace_id, _adv)
    require_feature("departments", workspace_id)
    name = request.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Department name is required")
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            INSERT INTO departments (workspace_id, name) VALUES (%s, %s)
            ON CONFLICT (workspace_id, name) DO NOTHING
            """,
            (workspace_id, name),
        )
        conn.commit()
        cur.execute(
            "SELECT department_id FROM departments WHERE workspace_id = %s AND name = %s",
            (workspace_id, name),
        )
        row = cur.fetchone()
    return {"department_id": str(row["department_id"]), "name": name}


@router.post("/debates/{debate_id}/department")
async def set_debate_department(
    debate_id: str,
    request: SetDepartmentRequest,
    _adv: Dict[str, Any] = Depends(require_role("advisor")),
):
    """Assign a session to a department (null clears it)."""
    workspace_id = _adv["workspace_id"]
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute("SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        if str(row["workspace_id"]) != workspace_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if request.department_id:
            _validate_uuid(request.department_id, "department_id")
            cur.execute(
                "SELECT 1 FROM departments WHERE department_id = %s AND workspace_id = %s",
                (request.department_id, workspace_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Department not found in this workspace")
        cur.execute(
            "UPDATE debates SET department_id = %s WHERE debate_id = %s",
            (request.department_id or None, debate_id),
        )
        conn.commit()
    return {"debate_id": debate_id, "department_id": request.department_id or None}


@router.post("/workspaces/{workspace_id}/invites")
async def create_invite(
    workspace_id: str,
    request: CreateInviteRequest,
    _adv: Dict[str, Any] = Depends(require_role("advisor")),
):
    """Mint a single-use invite token carrying a role (and optional department).
    Share the token; the invitee redeems it at POST /invites/{token}/accept."""
    _check_workspace(workspace_id, _adv)
    require_feature("invites", workspace_id)
    role = (request.role or "").strip().lower()
    if role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of {sorted(ASSIGNABLE_ROLES)}",
        )
    token = secrets.token_urlsafe(24)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        if request.department_id:
            _validate_uuid(request.department_id, "department_id")
            cur.execute(
                "SELECT 1 FROM departments WHERE department_id = %s AND workspace_id = %s",
                (request.department_id, workspace_id),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Department not found in this workspace")
        cur.execute(
            """
            INSERT INTO workspace_invites (invite_token, workspace_id, role, department_id, created_by, expires_at)
            VALUES (%s, %s, %s, %s, %s, now() + (%s || ' days')::interval)
            RETURNING expires_at
            """,
            (token, workspace_id, role, request.department_id or None,
             str(_adv.get("user_id") or ""), str(request.expires_days)),
        )
        row = cur.fetchone()
        conn.commit()
    return {
        "invite_token": token,
        "role": role,
        "workspace_id": workspace_id,
        "expires_at": row["expires_at"].isoformat(),
        "accept_path": f"/invites/{token}/accept",
    }


@router.get("/workspaces/{workspace_id}/invites")
async def list_invites(
    workspace_id: str,
    _adv: Dict[str, Any] = Depends(require_role("advisor")),
):
    """Open (unused, unexpired) invites for this workspace."""
    _check_workspace(workspace_id, _adv)
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            """
            SELECT invite_token, role, department_id, created_at, expires_at
            FROM workspace_invites
            WHERE workspace_id = %s AND used_at IS NULL AND expires_at > now()
            ORDER BY created_at DESC
            """,
            (workspace_id,),
        )
        rows = cur.fetchall()
    return {
        "workspace_id": workspace_id,
        "invites": [
            {
                "invite_token": r["invite_token"],
                "role": r["role"],
                "department_id": str(r["department_id"]) if r["department_id"] else None,
                "expires_at": r["expires_at"].isoformat(),
            }
            for r in rows
        ],
    }


@router.post("/invites/{token}/accept")
async def accept_invite(
    token: str,
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Redeem an invite: the authenticated caller joins the invite's workspace
    with the invite's role. Single-use; expired or spent tokens are rejected."""
    user_id = str(user.get("user_id") or "")
    try:
        uuid_lib.UUID(user_id)
    except ValueError:
        # Dev mode's synthetic 'test-user' has no UUID identity; membership
        # rows require one. Real Supabase-authenticated users always pass.
        raise HTTPException(
            status_code=400,
            detail="Invite acceptance requires an authenticated user (enable REQUIRE_AUTH)",
        )
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        cur.execute(
            "SELECT workspace_id, role, used_at, expires_at FROM workspace_invites "
            "WHERE invite_token = %s FOR UPDATE",
            (token,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        if row["used_at"] is not None:
            raise HTTPException(status_code=410, detail="Invite already used")
        cur.execute("SELECT now() AS now")
        if row["expires_at"] < cur.fetchone()["now"]:
            raise HTTPException(status_code=410, detail="Invite expired")
        workspace_id = str(row["workspace_id"])
        role = row["role"]
        cur.execute(
            """
            INSERT INTO user_workspaces (user_id, workspace_id, role)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, workspace_id) DO UPDATE SET role = EXCLUDED.role
            """,
            (user_id, workspace_id, role),
        )
        cur.execute(
            "UPDATE workspace_invites SET used_by = %s, used_at = now() WHERE invite_token = %s",
            (user_id, token),
        )
        conn.commit()
    return {"workspace_id": workspace_id, "role": role, "joined": True}
