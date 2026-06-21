"""Meeting setup service (M4 primitives).

Creates a debate plus participant + materials metadata. Does not call any LLMs.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras

from .agent_service import AgentService
from .database import get_db_connection, get_cursor
from .debate_service import DebateService


class MeetingSetupError(ValueError):
    """Bad request / validation error for setup flow."""


class MeetingSetupService:
    MAX_ACTIVE_PARTICIPANTS = 8

    def __init__(self) -> None:
        self._debates = DebateService()
        self._agents = AgentService()

    def create_setup(
        self,
        workspace_id: str,
        title: str,
        problem_statement: str,
        participants: List[Dict[str, Any]],
        materials: Optional[List[Dict[str, Any]]] = None,
        agenda: Optional[List[str]] = None,
        desired_outcomes: Optional[List[str]] = None,
        timebox_minutes: Optional[int] = None,
        max_rounds: Optional[int] = None,
        enable_host: Optional[bool] = False,
        host_model_id: Optional[str] = None,
        reasoning_mode: Optional[str] = "medium",
    ) -> Tuple[str, List[str], List[str]]:
        """
        Returns: (debate_id, participant_ids, material_ids)
        """
        # Allow creating debate without participants (for file uploads in Step 2)
        # Participants can be added later before launching
        participants = participants or []
        
        if len(participants) > self.MAX_ACTIVE_PARTICIPANTS:
            raise MeetingSetupError(
                f"participants exceeds maximum of {self.MAX_ACTIVE_PARTICIPANTS}"
            )

        policy_config: Dict[str, Any] = {
            "problem_statement": problem_statement,
        }
        if agenda:
            policy_config["agenda"] = agenda
        if desired_outcomes:
            policy_config["desired_outcomes"] = desired_outcomes
        if timebox_minutes is not None:
            policy_config["timebox_minutes"] = timebox_minutes
        if max_rounds is not None:
            policy_config["max_rounds"] = max_rounds
        if enable_host:
            policy_config["enable_host"] = enable_host
            policy_config["host_model_id"] = host_model_id or "openai/gpt-4o-mini"
        # Store reasoning mode so all services can pick the right model later
        policy_config["reasoning_mode"] = reasoning_mode or "medium"

        debate = self._debates.create_debate(
            workspace_id=workspace_id, title=title, policy_config=policy_config
        )
        debate_id = debate["debate_id"]

        participant_ids = self._insert_participants(
            workspace_id=workspace_id, debate_id=debate_id, participants=participants
        )
        material_ids = self._insert_materials(
            debate_id=debate_id, materials=materials or []
        )

        return debate_id, participant_ids, material_ids

    def _insert_participants(
        self,
        workspace_id: str,
        debate_id: str,
        participants: List[Dict[str, Any]],
    ) -> List[str]:
        now = datetime.now(timezone.utc)
        ids: List[str] = []

        with get_db_connection() as conn:
            cursor = get_cursor(conn)

            for p in participants:
                participant_id = str(uuid.uuid4())
                agent_config, role_name = self._normalize_participant(
                    workspace_id=workspace_id, participant=p
                )

                cursor.execute(
                    """
                    INSERT INTO participants (
                        participant_id, debate_id, participant_type, role_name,
                        agent_config, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        participant_id,
                        debate_id,
                        "agent",
                        role_name,
                        psycopg2.extras.Json(agent_config),
                        now,
                    ),
                )
                ids.append(participant_id)

        return ids

    def _normalize_participant(
        self, workspace_id: str, participant: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        """
        Accepts either:
        - {"agent_id": "..."} referencing a persistent agent
        - Inline config with required fields: name + system_prompt + model_id
        """
        agent_id = participant.get("agent_id")
        if agent_id:
            agent = self._agents.get_agent(agent_id)
            if not agent:
                raise MeetingSetupError(f"agent_id not found: {agent_id}")
            if str(agent["workspace_id"]) != str(workspace_id):
                raise MeetingSetupError("agent_id belongs to a different workspace")

            role_name = agent["name"]
            agent_config = {
                "agent_id": agent["agent_id"],
                "name": agent["name"],
                "role_description": agent.get("role_description"),
                "system_prompt": agent.get("system_prompt"),
                "model_id": agent.get("model_id"),
                "model_config": agent.get("model_config") or {},
                "source": "persistent_agent",
            }
            return agent_config, role_name

        # Inline config
        name = participant.get("name")
        system_prompt = participant.get("system_prompt")
        model_id = participant.get("model_id")
        if not name or not system_prompt or not model_id:
            raise MeetingSetupError(
                "Inline participants require name, system_prompt, and model_id"
            )

        role_name = name
        agent_config = {
            "name": name,
            "role_description": participant.get("role_description"),
            "system_prompt": system_prompt,
            "model_id": model_id,
            "model_config": participant.get("model_config") or {},
            "source": "inline",
        }
        return agent_config, role_name

    def _insert_materials(self, debate_id: str, materials: List[Dict[str, Any]]) -> List[str]:
        if not materials:
            return []

        now = datetime.now(timezone.utc)
        ids: List[str] = []

        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            for m in materials:
                material_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO meeting_materials (
                        material_id, debate_id, kind, title, body_text, url,
                        created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        material_id,
                        debate_id,
                        m.get("kind"),
                        m.get("title"),
                        m.get("body_text"),
                        m.get("url"),
                        now,
                        now,
                    ),
                )
                ids.append(material_id)

        # Chunk text/link materials so they are retrievable by prep + live turns
        # (file uploads are chunked by the Celery task; inline materials were not).
        from src.tasks.material_processing import chunk_inline_material
        for m, material_id in zip(materials, ids):
            kind = m.get("kind")
            try:
                if kind == "text" and (m.get("body_text") or "").strip():
                    chunk_inline_material(debate_id, material_id, m["body_text"], category="supplementary")
                elif kind == "link" and (m.get("url") or "").strip():
                    descriptor = f"Reference link: {m.get('title') or ''}\n{m.get('url')}".strip()
                    chunk_inline_material(debate_id, material_id, descriptor, category="supplementary")
            except Exception as exc:
                print(f"Inline material chunking failed (non-fatal) for {material_id}: {exc}")

        return ids

