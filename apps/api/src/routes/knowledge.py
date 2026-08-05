"""
Agent Knowledge Routes
Endpoints for accessing agent knowledge units (prep packs, etc.)
"""

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Header
from ..database import get_db_connection, get_cursor
from ..auth import get_current_user, require_auth, workspace_ids_for
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-knowledge", tags=["knowledge"])


@router.get("/{knowledge_id}")
async def get_knowledge_unit(
    knowledge_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Fetch a specific agent knowledge unit by ID.
    Returns the full content and metadata.
    """
    # require_auth returns only the caller's ACTIVE workspace, so a prep pack
    # in any of their other workspaces answered "not found or unauthorized" -
    # which is every prep pack, since preflight runs in the session's workspace
    # and not necessarily the one selected in the header.
    # Resolved via Depends, not by calling get_current_user() directly:
    # called as a plain function its x_workspace_id parameter binds to its
    # own default, a fastapi Header(None) OBJECT, which is truthy. That was
    # read as "the caller asked for a specific workspace", and every request
    # got 403 "not a member of the requested workspace" — so View Prep Pack
    # failed for everyone, on every session.
    workspace_ids = workspace_ids_for(current_user)
    
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        try:
            # Fetch knowledge unit with workspace authorization check
            cursor.execute("""
                SELECT 
                    aku.knowledge_id,
                    aku.agent_id,
                    aku.source_debate_id,
                    aku.knowledge_type,
                    aku.content,
                    aku.metadata,
                    aku.created_at
                FROM agent_knowledge_units aku
                -- INNER JOIN, and no "OR d.workspace_id IS NULL".
                --
                -- It was a LEFT JOIN with that OR, so a unit whose debate link
                -- was NULL matched for EVERY caller. The FK is ON DELETE SET
                -- NULL, so deleting a session silently turned its prep packs
                -- into world-readable rows — measured on the live database,
                -- all 16 units were in that state. A prep pack nobody can
                -- attribute to a session is not a prep pack anyone may read.
                JOIN debates d ON aku.source_debate_id = d.debate_id
                WHERE aku.knowledge_id = %s
                  -- ::uuid[] because workspace_ids_for returns strings while
                  -- debates.workspace_id is uuid; without the cast Postgres
                  -- raises "operator does not exist: uuid = text", which the
                  -- bare except below re-raised as a 500.
                  AND d.workspace_id = ANY(%s::uuid[])
            """, (knowledge_id, workspace_ids))
            
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="Knowledge unit not found or unauthorized")
            
            return {
                "knowledge_id": result['knowledge_id'],
                "agent_id": result['agent_id'],
                "source_debate_id": result['source_debate_id'],
                "knowledge_type": result['knowledge_type'],
                "content": result['content'],
                "metadata": result['metadata'],
                "created_at": result['created_at'].isoformat() if result['created_at'] else None
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching knowledge unit: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to fetch knowledge unit: {str(e)}")
        finally:
            cursor.close()
