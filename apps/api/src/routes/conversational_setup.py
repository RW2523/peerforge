"""
Conversational setup
====================
POST /debates/{id}/setup/converse  → one turn of dialogue, returns a proposal
POST /debates/{id}/setup/apply     → materialise a proposal into a real panel

The debate is created first (empty), material is uploaded to it, and the
conversation is grounded in that material. Applying staffs the panel and
writes the policy, leaving the session ready to start.
"""
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import authorize_debate, get_current_user
from ..config import resolve_openrouter_key
from ..database import get_cursor, get_db_connection
from ..meeting_setup_service import MeetingSetupService
from ..services.conversational_setup import REVIEWER_ROLES, converse
from ..services.persona_prompts import get_base_prompt

router = APIRouter(tags=["conversational-setup"])

# Sessions that have begun speaking. Replacing a panel here would delete the
# reviewers whose turns are already in the transcript. Named as a blocklist
# rather than an allowlist because the pre-start states vary ('draft',
# 'pending', and whatever setup adds next) while "under way" does not.
_STATES_UNDER_WAY = frozenset({"running", "paused", "ended", "completed", "concluded"})


class Turn(BaseModel):
    role: str
    content: str


class ConverseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    history: List[Turn] = Field(default_factory=list)
    model_id: Optional[str] = None


class PanelMember(BaseModel):
    name: str
    role: str
    focus: Optional[str] = ""


class ApplyRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    problem_statement: str = Field(..., min_length=1, max_length=2000)
    panel: List[PanelMember] = Field(..., min_length=2, max_length=6)
    rounds: int = Field(3, ge=1, le=10)
    model_id: Optional[str] = None


@router.post("/debates/{debate_id}/setup/converse")
async def setup_converse(
    debate_id: str,
    request: ConverseRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """One turn of setup dialogue, grounded in the session's uploaded material."""
    authorize_debate(debate_id, current_user)
    x_openrouter_key = resolve_openrouter_key(x_openrouter_key)

    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An OpenRouter key is required. Add one in Settings.",
        )

    # Off the event loop: this spends tens of seconds inside LLM HTTP calls,
    # and run directly it froze every other request on the instance.
    return await asyncio.to_thread(
        converse,
        debate_id=debate_id,
        message=request.message,
        history=[t.model_dump() for t in request.history],
        openrouter_key=x_openrouter_key,
        model_id=request.model_id,
    )


@router.post("/debates/{debate_id}/setup/apply")
async def setup_apply(
    debate_id: str,
    request: ApplyRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Turn an agreed proposal into a staffed session.

    Idempotent in the sense that re-applying replaces the panel rather than
    appending to it — otherwise revising the proposal would double the panel.
    """
    authorize_debate(debate_id, current_user)

    roles = [m.role.strip().lower() for m in request.panel]
    unknown = [r for r in roles if r not in REVIEWER_ROLES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown reviewer role(s): {', '.join(sorted(set(unknown)))}",
        )

    model_id = request.model_id or "openai/gpt-4o-mini"
    participants = []
    for member in request.panel:
        role = member.role.strip().lower()
        participants.append({
            "name": member.name.strip()[:80],
            # role_description drives lane assignment and schema selection.
            "role_description": role,
            "system_prompt": _persona_prompt(role, member.focus or ""),
            "model_id": model_id,
        })

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            "SELECT workspace_id, policy_config, state FROM debates WHERE debate_id = %s",
            (debate_id,),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        workspace_id = str(row["workspace_id"])

        # Applying replaces the panel, so it may only run before the session
        # has said anything. Without this check, re-applying a proposal to a
        # session already under way deleted the reviewers mid-review, orphaning
        # every turn they had produced.
        state = (row["state"] or "").lower()
        if state in _STATES_UNDER_WAY:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This session is {state}; its panel can no longer be "
                       "replaced. Start a new session to use a different panel.",
            )

        # Replace rather than append: revising a proposal must not stack panels.
        cursor.execute("DELETE FROM participants WHERE debate_id = %s", (debate_id,))

        policy = dict(row["policy_config"] or {})
        policy.update({
            "max_rounds": request.rounds,
            "problem_statement": request.problem_statement,
            "setup_mode": "conversational",
        })
        cursor.execute(
            """UPDATE debates
               SET title = %s, policy_config = %s, updated_at = NOW()
               WHERE debate_id = %s""",
            (request.title, _json(policy), debate_id),
        )
        conn.commit()

    participant_ids = MeetingSetupService()._insert_participants(
        workspace_id=workspace_id,
        debate_id=debate_id,
        participants=participants,
    )

    return {
        "debate_id": debate_id,
        "title": request.title,
        "participant_ids": participant_ids,
        "rounds": request.rounds,
        "ready_to_start": True,
    }


def _persona_prompt(role: str, focus: str) -> str:
    """Canonical persona prompt, narrowed by what the researcher asked for."""
    try:
        base = get_base_prompt(role)
    except Exception:
        base = f"You are a {role} reviewing academic work."
    return f"{base}\n\nFor this session, focus on: {focus}" if focus else base


def _json(value: Dict[str, Any]):
    import psycopg2.extras
    return psycopg2.extras.Json(value)
