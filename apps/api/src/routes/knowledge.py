"""
Agent Knowledge Routes
Endpoints for accessing agent knowledge units (prep packs, etc.)
"""

from fastapi import APIRouter, HTTPException, Header
from ..database import get_db_connection, get_cursor
from ..auth import get_current_user, require_auth, workspace_ids_for
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-knowledge", tags=["knowledge"])


@router.get("/{knowledge_id}")
async def get_knowledge_unit(
    knowledge_id: str,
    authorization: str = Header(None)
):
    """
    Fetch a specific agent knowledge unit by ID.
    Returns the full content and metadata.
    """
    # require_auth returns only the caller's ACTIVE workspace, so a prep pack
    # in any of their other workspaces answered "not found or unauthorized" -
    # which is every prep pack, since preflight runs in the session's workspace
    # and not necessarily the one selected in the header.
    current_user = get_current_user(authorization)
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
                LEFT JOIN debates d ON aku.source_debate_id = d.debate_id
                WHERE aku.knowledge_id = %s
                  AND (d.workspace_id = ANY(%s) OR d.workspace_id IS NULL)
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
