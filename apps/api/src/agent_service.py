"""Persistent agent service (M4 meeting setup primitives).

Keeps agent CRUD separate from DebateService to stay within service file limits.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2.extras

from .database import get_db_connection, get_cursor


class AgentService:
    """CRUD for persistent agent definitions."""

    def create_agent(
        self,
        workspace_id: str,
        name: str,
        system_prompt: str,
        model_id: str,
        role_description: Optional[str] = None,
        model_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        agent_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        model_config_json = psycopg2.extras.Json(model_config or {})

        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute(
                """
                INSERT INTO agents (
                    agent_id, workspace_id, name, role_description, system_prompt,
                    model_id, model_config, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING agent_id, workspace_id, name, role_description,
                          system_prompt, model_id, model_config, created_at
                """,
                (
                    agent_id,
                    workspace_id,
                    name,
                    role_description,
                    system_prompt,
                    model_id,
                    model_config_json,
                    now,
                    now,
                ),
            )
            row = cursor.fetchone()
            return dict(row)

    def list_agents(self, workspace_id: str) -> List[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute(
                """
                SELECT agent_id, workspace_id, name, role_description, system_prompt,
                       model_id, model_config, created_at
                FROM agents
                WHERE workspace_id = %s
                ORDER BY created_at ASC
                """,
                (workspace_id,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute(
                """
                SELECT agent_id, workspace_id, name, role_description, system_prompt,
                       model_id, model_config, created_at
                FROM agents
                WHERE agent_id = %s
                """,
                (agent_id,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None

