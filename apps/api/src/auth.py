"""Supabase Auth JWT validation and authorization"""
import jwt
from typing import Optional, Dict, Any, List
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


def get_workspaces_for_user(user_id: str, email: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Every workspace the user belongs to, most recently joined first.

    Returns a list because a user legitimately belongs to many workspaces — a
    professor to their department and each course they teach. Resolving to a
    single workspace here silently hides all but one of them.
    """
    from .database import get_db_connection, get_cursor
    import uuid as _uuid

    # user_workspaces.user_id is UUID-typed, so a non-UUID subject can have no
    # membership by construction. Checking here keeps a malformed token from
    # surfacing as a database error.
    try:
        _uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return []

    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT uw.workspace_id, uw.role, w.name, w.tenant_id
                FROM user_workspaces uw
                JOIN workspaces w ON w.workspace_id = uw.workspace_id
                WHERE uw.user_id = %s
                ORDER BY uw.created_at DESC
            """, (user_id,))

            rows = cursor.fetchall()
            if rows:
                return [_membership(r) for r in rows]

            # An invited user must land in the organization that invited them.
            # Provisioning a personal workspace first would strand them: they
            # would hold a workspace nobody else can see and no path into the
            # course they were invited to.
            joined = _accept_pending_invitation(conn, cursor, user_id, email)
            if joined:
                return joined

            # Lazy provisioning: a Supabase auth user reaching the PeerForge API
            # for the first time gets their own isolated workspace. This avoids a
            # trigger on auth.users — important when the Supabase project is shared
            # with another app, whose signups must not create PeerForge workspaces.
            provisioned = _provision_workspace_for_user(conn, cursor, user_id)
            return [provisioned] if provisioned else []
    except Exception as exc:
        # A database failure is not the same as "this user has no workspace".
        # Returning [] here would render as a 403 and look like an access
        # decision, hiding the outage.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not resolve workspace membership: {exc}"
        )


# Org roles that carry authority over every workspace in the organization.
ELEVATED_ORG_ROLES = ('org_admin', 'professor', 'ta')


def get_organizations_for_user(user_id: str) -> List[Dict[str, Any]]:
    """Organizations (universities) the user belongs to, with their role."""
    from .database import get_db_connection, get_cursor
    import uuid as _uuid

    try:
        _uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return []

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("""
            SELECT om.org_id, om.org_role, t.name, t.slug
            FROM organization_members om
            JOIN tenants t ON t.tenant_id = om.org_id
            WHERE om.user_id = %s
            ORDER BY om.created_at ASC
        """, (user_id,))
        return [
            {
                'org_id': str(r['org_id']),
                'org_role': r['org_role'],
                'name': r['name'],
                'slug': r['slug'],
            }
            for r in cursor.fetchall()
        ]


def get_accessible_workspace_ids(user_id: str, memberships: List[Dict[str, Any]]) -> List[str]:
    """
    Every workspace the user may reach: their own enrolments, plus every
    workspace in an organization where they hold an elevated role.

    Computed once per request so authorization stays a set lookup — a
    professor opening a student's session must not cost an extra query on
    every access check.
    """
    from .database import get_db_connection, get_cursor
    import uuid as _uuid

    ids = {m['workspace_id'] for m in memberships}

    try:
        _uuid.UUID(str(user_id))
    except (ValueError, AttributeError, TypeError):
        return sorted(ids)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("""
            SELECT w.workspace_id
            FROM organization_members om
            JOIN workspaces w ON w.tenant_id = om.org_id
            WHERE om.user_id = %s AND om.org_role = ANY(%s)
        """, (user_id, list(ELEVATED_ORG_ROLES)))
        ids.update(str(r['workspace_id']) for r in cursor.fetchall())

    return sorted(ids)


def org_role_in(user: Dict[str, Any], org_id: str) -> Optional[str]:
    """The user's role in a given organization, or None if not a member."""
    for o in user.get('organizations') or []:
        if o['org_id'] == str(org_id):
            return o['org_role']
    return None


def require_org_role(user: Dict[str, Any], org_id: str, *allowed: str) -> str:
    """Assert the caller holds one of `allowed` roles in the organization."""
    role = org_role_in(user, org_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this organization"
        )
    if allowed and role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of: {', '.join(allowed)} (you are {role})"
        )
    return role


def _membership(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        'workspace_id': str(row['workspace_id']),
        'role': row['role'],
        'name': row.get('name'),
        'tenant_id': str(row['tenant_id']) if row.get('tenant_id') else None,
    }


def get_workspace_for_user(user_id: str) -> Optional[str]:
    """The user's default (most recent) workspace id, or None."""
    memberships = get_workspaces_for_user(user_id)
    return memberships[0]['workspace_id'] if memberships else None


def _accept_pending_invitation(conn, cursor, user_id: str, email: Optional[str]):
    """
    Redeem the newest pending invitation for this email address, if any.

    Returns the resulting memberships, or None when there is nothing to redeem
    so the caller can fall back to provisioning a personal workspace.
    """
    if not email:
        return None

    cursor.execute("""
        SELECT token FROM invitations
        WHERE LOWER(email) = LOWER(%s)
          AND accepted_at IS NULL
          AND revoked_at IS NULL
          AND expires_at > NOW()
        ORDER BY created_at DESC
        LIMIT 1
    """, (email,))
    row = cursor.fetchone()
    if not row:
        return None

    try:
        from .routes.organizations import redeem_invitation
        redeem_invitation(cursor, row['token'], user_id)
        conn.commit()
    except Exception as exc:
        conn.rollback()
        print(f"[auth] Could not redeem invitation for {email}: {exc}")
        return None

    cursor.execute("""
        SELECT uw.workspace_id, uw.role, w.name, w.tenant_id
        FROM user_workspaces uw
        JOIN workspaces w ON w.workspace_id = uw.workspace_id
        WHERE uw.user_id = %s
        ORDER BY uw.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()
    return [_membership(r) for r in rows] if rows else None


# Default tenant that owns auto-provisioned personal workspaces.
_DEFAULT_TENANT_ID = '00000000-0000-0000-0000-000000000001'


def _provision_workspace_for_user(conn, cursor, user_id: str) -> Optional[Dict[str, Any]]:
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
    return {
        'workspace_id': workspace_id,
        'role': 'owner',
        'name': f'Workspace {short}',
        'tenant_id': _DEFAULT_TENANT_ID,
    }


# A real UUID so dev matches production, where `sub` is always one
# and UUID-typed columns such as debates.owner_user_id accept it.
DEV_USER_ID = '00000000-0000-0000-0000-0000000000de'
DEV_WORKSPACE_ID = '00000000-0000-0000-0000-000000000101'
DEV_TENANT_ID = '00000000-0000-0000-0000-000000000001'


def get_current_user(
    authorization: str = Header(None),
    x_workspace_id: Optional[str] = Header(None),
) -> Dict[str, Any]:
    """
    Extract and validate current user from JWT.

    Returns every workspace the user belongs to plus one designated active
    workspace. Clients select the active one with the X-Workspace-Id header;
    without it the most recently joined workspace is used.

    Raises:
        HTTPException: 401 if token missing/invalid, 403 if the requested
        active workspace is not one the user belongs to.
    """
    if not settings.require_auth:
        # Auth disabled for local dev/testing. The workspace selector is still
        # validated so dev behaves like production on this dimension — asking
        # for a workspace you don't belong to fails here too.
        dev_memberships = [{
            'workspace_id': DEV_WORKSPACE_ID,
            'role': 'owner',
            'name': 'Local Dev',
            'tenant_id': DEV_TENANT_ID,
        }]
        active = _select_active_workspace(dev_memberships, x_workspace_id)
        return {
            'user_id': DEV_USER_ID,
            'workspace_id': active['workspace_id'],
            'tenant_id': active['tenant_id'],
            'workspaces': dev_memberships,
            'workspace_ids': [DEV_WORKSPACE_ID],
            'workspace_role': active['role'],
            'organizations': [{
                'org_id': DEV_TENANT_ID,
                'org_role': 'org_admin',
                'name': 'Local Dev',
                'slug': 'local-dev',
            }],
        }

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = decode_jwt(authorization)

        user_id = payload.get('sub')  # Supabase user ID
        if not user_id:
            raise AuthError("Token missing user ID (sub)")

        memberships = get_workspaces_for_user(user_id, payload.get('email'))
        organizations = get_organizations_for_user(user_id)
        accessible = get_accessible_workspace_ids(user_id, memberships)

        # A workspace_id claim selects among the caller's workspaces; it does
        # not confer access. Membership in user_workspaces is the authority, so
        # a crafted or stale claim cannot reach another tenant.
        requested = x_workspace_id or payload.get('workspace_id')
        active = _select_active_workspace(memberships, requested, accessible)

        return {
            'user_id': user_id,
            'workspace_id': active['workspace_id'] if active else None,
            'workspace_role': active['role'] if active else None,
            'tenant_id': (active or {}).get('tenant_id') or payload.get('tenant_id'),
            'workspaces': memberships,
            'workspace_ids': accessible,
            'organizations': organizations,
            'email': payload.get('email'),
            'role': payload.get('role')
        }

    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"}
        )


def _select_active_workspace(
    memberships: List[Dict[str, Any]],
    requested_id: Optional[str],
    accessible_ids: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick the active workspace, rejecting one the caller cannot reach.

    A professor may make a course they are not enrolled in active, provided
    their organization role grants access to it.
    """
    if not requested_id:
        return memberships[0] if memberships else None

    for m in memberships:
        if m['workspace_id'] == requested_id:
            return m

    if accessible_ids and requested_id in accessible_ids:
        # Reachable through an organization role rather than enrolment.
        return {
            'workspace_id': requested_id,
            'role': None,
            'name': None,
            'tenant_id': None,
        }

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Access denied: not a member of the requested workspace"
    )


def check_workspace_access(
    user: Dict[str, Any],
    resource_workspace_id: str
) -> None:
    """
    Verify the user belongs to the resource's workspace.

    Checks membership across every workspace the user belongs to, not just the
    active one — otherwise a professor viewing a second course would be denied
    purely because of which workspace happened to be selected.

    Raises:
        HTTPException: 403 if user lacks access
    """
    member_of = workspace_ids_for(user)

    if not member_of:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any workspace"
        )

    if resource_workspace_id is None or str(resource_workspace_id) not in member_of:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: resource belongs to a different workspace"
        )


def authorize_debate(debate_id: str, user: Dict[str, Any]) -> str:
    """
    Resolve a debate's workspace and confirm the caller belongs to it.

    Returns the workspace id so callers can reuse it. Route handlers that take
    a debate_id must go through this — reading the caller's own workspace and
    not comparing it to the debate's is how cross-tenant reads happen.
    """
    from .database import get_db_connection, get_cursor
    import uuid as _uuid

    # A malformed id is a missing debate, not a database type error.
    try:
        _uuid.UUID(str(debate_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            "SELECT workspace_id FROM debates WHERE debate_id = %s", (debate_id,)
        )
        row = cursor.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debate {debate_id} not found"
        )

    workspace_id = str(row['workspace_id'])
    check_workspace_access(user, workspace_id)
    return workspace_id


def workspace_ids_for(user: Dict[str, Any]) -> List[str]:
    """Workspace ids a user belongs to, tolerating the older single-id shape."""
    ids = user.get('workspace_ids')
    if ids:
        return [str(i) for i in ids]
    active = user.get('workspace_id')
    return [str(active)] if active else []


def role_in_workspace(user: Dict[str, Any], workspace_id: str) -> Optional[str]:
    """The user's role in a given workspace, or None if not a member."""
    for m in user.get('workspaces') or []:
        if m['workspace_id'] == str(workspace_id):
            return m['role']
    return None


def require_auth(
    authorization: str = Header(None),
    x_workspace_id: Optional[str] = Header(None),
) -> str:
    """
    Convenience dependency for routes that only need the active workspace id.

    Prefer Depends(get_current_user) plus check_workspace_access when the route
    touches a specific resource — this returns the caller's own workspace and
    cannot tell you whether they may reach the resource they asked for.

    Raises:
        HTTPException: 401 if token missing/invalid
    """
    user = get_current_user(authorization, x_workspace_id)
    workspace_id = user.get('workspace_id')

    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not associated with any workspace"
        )

    return workspace_id
