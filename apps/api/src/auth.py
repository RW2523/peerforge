"""Supabase Auth JWT validation and authorization"""
import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Header
from .config import settings


async def get_current_user_ws(token: str) -> Dict[str, Any]:
    """
    Get current user from WebSocket auth token.
    Normalizes user shape to match HTTP auth behavior.
    
    Args:
        token: JWT token from query param
    
    Returns:
        User info dict with sub, workspace_id, tenant_id
    
    Raises:
        HTTPException: 401 if invalid
    """
    try:
        payload = decode_jwt(token)
        
        # Ensure workspace_id is present (resolve from user_workspaces if needed)
        if 'workspace_id' not in payload or not payload['workspace_id']:
            user_id = payload.get('sub')
            if user_id:
                workspace_id = get_workspace_for_user(user_id)
                if workspace_id:
                    payload['workspace_id'] = workspace_id
        
        # Validate required claims
        if not payload.get('sub'):
            raise AuthError("Token missing 'sub' claim")
        
        return payload
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


class AuthError(Exception):
    """Authentication/authorization error"""
    pass


def decode_jwt(token: str) -> Dict[str, Any]:
    """
    Decode and validate Supabase JWT token
    
    Args:
        token: JWT token from Authorization header
    
    Returns:
        Decoded token payload with user_id, workspace_id, tenant_id
    
    Raises:
        AuthError: Invalid token
    """
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
        
        # Decode JWT with Supabase secret
        # Disable iat verification to avoid clock skew issues
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=['HS256'],
            options={'verify_exp': True, 'verify_iat': False}
        )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.InvalidSignatureError:
        raise AuthError("Invalid token signature")
    except jwt.DecodeError:
        raise AuthError("Invalid token format")
    except Exception as e:
        raise AuthError(f"Token validation failed: {str(e)}")


def get_workspace_for_user(user_id: str) -> Optional[str]:
    """
    Resolve workspace_id for user from user_workspaces table
    
    Args:
        user_id: Supabase user ID
    
    Returns:
        workspace_id or None if user not mapped to any workspace
    """
    from .database import get_db_connection, get_cursor

    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT workspace_id, role
                FROM user_workspaces
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """, (user_id,))

            result = cursor.fetchone()
            if result:
                return str(result['workspace_id'])

            # Lazy provisioning: a Supabase auth user reaching the PeerForge API
            # for the first time gets their own isolated workspace. This avoids a
            # trigger on auth.users — important when the Supabase project is shared
            # with another app, whose signups must not create PeerForge workspaces.
            return _provision_workspace_for_user(conn, cursor, user_id)
    except Exception:
        # If DB query fails, return None (will be handled by caller)
        return None


# Default tenant that owns auto-provisioned personal workspaces.
_DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000001'


def _provision_workspace_for_user(conn, cursor, user_id: str) -> Optional[str]:
    """Create a personal workspace for a first-time PeerForge user and map them to it."""
    import uuid

    workspace_id = str(uuid.uuid4())
    short = str(user_id).replace('-', '')[:8]

    cursor.execute("""
        INSERT INTO tenants (tenant_id, name, slug)
        VALUES (%s, 'PeerForge', 'peerforge')
        ON CONFLICT (tenant_id) DO NOTHING
    """, (_DEFAULT_TENANT_ID,))

    cursor.execute("""
        INSERT INTO workspaces (workspace_id, tenant_id, name, slug)
        VALUES (%s, %s, %s, %s)
    """, (workspace_id, _DEFAULT_TENANT_ID, f'Workspace {short}', f'ws-{short}-{workspace_id[:8]}'))

    cursor.execute("""
        INSERT INTO user_workspaces (user_id, workspace_id, role)
        VALUES (%s, %s, 'owner')
        ON CONFLICT (user_id, workspace_id) DO NOTHING
    """, (user_id, workspace_id))

    conn.commit()
    return workspace_id


def get_current_user(authorization: str = Header(None)) -> Dict[str, Any]:
    """
    Extract and validate current user from JWT
    
    Args:
        authorization: Authorization header value
    
    Returns:
        User info dict with user_id, workspace_id, tenant_id
    
    Raises:
        HTTPException: 401 if token missing/invalid
    """
    if not settings.require_auth:
        # Auth disabled for local dev/testing
        return {
            'user_id': 'test-user',
            'workspace_id': '00000000-0000-0000-0000-000000000101',
            'tenant_id': '00000000-0000-0000-0000-000000000001'
        }
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    try:
        payload = decode_jwt(authorization)
        
        # Extract user context from JWT payload
        user_id = payload.get('sub')  # Supabase user ID
        workspace_id = payload.get('workspace_id')
        tenant_id = payload.get('tenant_id')
        
        if not user_id:
            raise AuthError("Token missing user ID (sub)")
        
        # If workspace_id not in JWT, resolve from user_workspaces table
        if not workspace_id:
            workspace_id = get_workspace_for_user(user_id)
        
        return {
            'user_id': user_id,
            'workspace_id': workspace_id,
            'tenant_id': tenant_id,
            'email': payload.get('email'),
            'role': payload.get('role')
        }
    
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


def check_workspace_access(
    user: Dict[str, Any],
    resource_workspace_id: str
) -> None:
    """
    Verify user has access to workspace
    
    Args:
        user: User context from JWT
        resource_workspace_id: Workspace ID of requested resource
    
    Raises:
        HTTPException: 403 if user lacks access
    """
    user_workspace_id = user.get('workspace_id')
    
    if not user_workspace_id:
        # No workspace claim in token - deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any workspace"
        )
    
    if user_workspace_id != resource_workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: debate belongs to different workspace"
        )


def require_auth(authorization: str = Header(None)) -> str:
    """
    Convenience dependency for routes that just need workspace_id
    
    Args:
        authorization: Authorization header value
    
    Returns:
        workspace_id string
    
    Raises:
        HTTPException: 401 if token missing/invalid
    """
    user = get_current_user(authorization)
    workspace_id = user.get('workspace_id')

    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any workspace"
        )

    return workspace_id


# ── Role-based access control (B1) ─────────────────────────────────────────

def get_role_for_user(user_id: str, workspace_id: str) -> Optional[str]:
    """The user's role in a workspace, from user_workspaces. None when no
    membership row exists (callers treat that as least privilege)."""
    try:
        from .database import get_db_connection, get_cursor
        with get_db_connection() as conn:
            cur = get_cursor(conn)
            cur.execute(
                "SELECT role FROM user_workspaces WHERE user_id = %s AND workspace_id = %s",
                (user_id, workspace_id),
            )
            row = cur.fetchone()
            return row["role"] if row else None
    except Exception:
        return None


def require_role(*allowed_roles: str):
    """Dependency factory: the caller must hold one of *allowed_roles* in their
    workspace. 'owner' always passes (a workspace owner outranks every role).

    Dev mode (REQUIRE_AUTH=false) resolves the test user's role from the DB the
    same way, defaulting to 'owner' if no membership row exists — so local dev
    keeps full access while the enforcement path stays real.
    """
    # 'owner' outranks every role; legacy 'admin' rows are owner-equivalent.
    allowed = set(allowed_roles) | {"owner", "admin"}

    def _dep(authorization: str = Header(None)) -> Dict[str, Any]:
        user = get_current_user(authorization)
        workspace_id = user.get("workspace_id")
        if not workspace_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="User not associated with any workspace")
        # user_workspaces is the authority on workspace roles. The JWT's own
        # 'role' claim is Supabase's postgres role ('authenticated') — never
        # an app role, so it must not short-circuit the DB lookup.
        role = get_role_for_user(user.get("user_id", ""), workspace_id)
        if role is None and not settings.require_auth:
            # No membership row for the dev test user — keep dev unblocked.
            # A real membership row (even 'student') is always honored.
            role = "owner"
        role = role or "student"
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles {sorted(allowed)}; you have '{role}'",
            )
        return {**user, "role": role}

    return _dep
