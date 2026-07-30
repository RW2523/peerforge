"""
Identity and membership discovery
=================================
GET /me                → who am I, and which workspace am I acting in
GET /me/workspaces     → every workspace I belong to, with my role in each

The frontend needs these to stop hardcoding a workspace id. Clients pick an
active workspace by sending X-Workspace-Id on subsequent requests; membership
is verified server-side, so the header selects but never grants.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..auth import get_current_user

router = APIRouter(tags=["me"])


@router.get("/me")
async def whoami(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Current identity plus the active workspace and role."""
    return {
        "user_id": current_user.get("user_id"),
        "email": current_user.get("email"),
        "active_workspace_id": current_user.get("workspace_id"),
        "active_workspace_role": current_user.get("workspace_role"),
        "tenant_id": current_user.get("tenant_id"),
        "workspace_count": len(current_user.get("workspaces") or []),
    }


@router.get("/me/workspaces")
async def my_workspaces(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Every workspace the caller belongs to, most recently joined first."""
    workspaces = current_user.get("workspaces") or []
    active_id = current_user.get("workspace_id")

    return {
        "active_workspace_id": active_id,
        "workspaces": [
            {
                "workspace_id": w["workspace_id"],
                "name": w.get("name"),
                "role": w.get("role"),
                "tenant_id": w.get("tenant_id"),
                "is_active": w["workspace_id"] == active_id,
            }
            for w in workspaces
        ],
    }
