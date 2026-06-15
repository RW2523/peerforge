"""
Transcript action items & panel decision discussions.

Flow:
1. Extract action items from a meeting transcript material (LLM).
2. List / edit those action items.
3. Spawn a short autonomous panel discussion to decide one (reuses the debate engine).
4. Poll the decision once the child debate concludes.
"""

import json
import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel

from ..database import get_db_connection, get_cursor
from ..auth import require_auth
from ..openrouter_client import OpenRouterClient
from ..meeting_setup_service import MeetingSetupService
from ..summary_service import SummaryService
from ..autonomous_debate_service import autonomous_service

router = APIRouter()

# Default model for action-item extraction and the small decision panel
DEFAULT_MODEL = "openai/gpt-4o-mini"
# Decision debates are intentionally short
DECISION_MAX_ROUNDS = 2
DECISION_TURN_DELAY = 4


# ── Schemas ────────────────────────────────────────────────────────────────

class ActionItem(BaseModel):
    action_id: str
    material_id: Optional[str] = None
    description: str
    owner: Optional[str] = None
    priority: str = "medium"
    status: str = "extracted"
    decision_debate_id: Optional[str] = None
    decision: Optional[str] = None
    decision_rationale: Optional[str] = None
    seq_order: int = 0


class ActionItemUpdate(BaseModel):
    description: Optional[str] = None
    owner: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None


class DecisionResponse(BaseModel):
    action_id: str
    status: str  # debating | decided
    decision_debate_id: Optional[str] = None
    decision: Optional[str] = None
    decision_rationale: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────

def _verify_debate(cursor, debate_id: str, workspace_id: str) -> dict:
    cursor.execute(
        "SELECT debate_id, workspace_id, title, policy_config FROM debates WHERE debate_id = %s",
        (debate_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Debate not found")
    if str(row["workspace_id"]) != workspace_id:
        raise HTTPException(status_code=403, detail="Access denied to this debate")
    return dict(row)


def _row_to_action_item(row: dict) -> ActionItem:
    return ActionItem(
        action_id=str(row["action_id"]),
        material_id=str(row["material_id"]) if row.get("material_id") else None,
        description=row["description"],
        owner=row.get("owner"),
        priority=row.get("priority") or "medium",
        status=row.get("status") or "extracted",
        decision_debate_id=str(row["decision_debate_id"]) if row.get("decision_debate_id") else None,
        decision=row.get("decision"),
        decision_rationale=row.get("decision_rationale"),
        seq_order=row.get("seq_order") or 0,
    )


def _parse_action_items(content: str) -> List[dict]:
    """Best-effort extraction of a JSON array of action items from an LLM response."""
    # Strip code fences
    cleaned = re.sub(r"^```(?:json)?|```$", "", content.strip(), flags=re.MULTILINE).strip()
    # Find the first JSON array
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        cleaned = match.group(0)
    try:
        data = json.loads(cleaned)
    except Exception:
        return []
    items = []
    for entry in data if isinstance(data, list) else []:
        if isinstance(entry, str):
            items.append({"description": entry, "owner": None, "priority": "medium"})
        elif isinstance(entry, dict) and entry.get("description"):
            priority = (entry.get("priority") or "medium").lower()
            if priority not in ("low", "medium", "high"):
                priority = "medium"
            items.append({
                "description": str(entry["description"]),
                "owner": entry.get("owner"),
                "priority": priority,
            })
    return items


# ── Extract ────────────────────────────────────────────────────────────────

@router.post("/debates/{debate_id}/materials/{material_id}/extract-action-items",
             response_model=List[ActionItem])
async def extract_action_items(
    debate_id: str,
    material_id: str,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    workspace_id: str = Depends(require_auth),
):
    """Extract action items from a transcript material and store them."""
    if not x_openrouter_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key required (X-OpenRouter-Key)")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        _verify_debate(cursor, debate_id, workspace_id)

        # Load transcript text: prefer body_text, else stitch its chunks together
        cursor.execute(
            "SELECT body_text, material_category FROM meeting_materials WHERE material_id = %s AND debate_id = %s",
            (material_id, debate_id),
        )
        mat = cursor.fetchone()
        if not mat:
            raise HTTPException(status_code=404, detail="Transcript material not found")

        transcript = (mat.get("body_text") or "").strip()
        if not transcript:
            cursor.execute(
                """
                SELECT chunk_text FROM memory_chunks
                WHERE source_debate_id = %s AND agent_id IS NULL
                  AND chunk_metadata->>'material_id' = %s
                ORDER BY (chunk_metadata->>'chunk_index')::int NULLS LAST
                """,
                (debate_id, material_id),
            )
            transcript = "\n".join(r["chunk_text"] for r in cursor.fetchall()).strip()

        if not transcript:
            raise HTTPException(status_code=400, detail="Transcript has no text yet (still processing?)")

    # LLM extraction (truncate very long transcripts for the prompt)
    prompt_text = transcript[:12000]
    client = OpenRouterClient(x_openrouter_key)
    completion = client.chat_completion(
        model=DEFAULT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract concrete action items from meeting transcripts. "
                    "Return ONLY a JSON array. Each element: "
                    '{"description": str, "owner": str|null, "priority": "low"|"medium"|"high"}. '
                    "Be specific and actionable; no commentary outside the JSON."
                ),
            },
            {"role": "user", "content": f"Transcript:\n\n{prompt_text}"},
        ],
        temperature=0.3,
        max_tokens=1200,
        _debate_id=debate_id,
        _stage="action_item_extraction",
    )

    parsed = _parse_action_items(completion.get("content", ""))
    if not parsed:
        raise HTTPException(status_code=422, detail="Could not extract action items from transcript")

    created: List[ActionItem] = []
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        for idx, item in enumerate(parsed):
            action_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO transcript_action_items (
                    action_id, debate_id, material_id, description, owner, priority, status, seq_order
                ) VALUES (%s, %s, %s, %s, %s, %s, 'extracted', %s)
                RETURNING action_id, material_id, description, owner, priority, status,
                          decision_debate_id, decision, decision_rationale, seq_order
                """,
                (action_id, debate_id, material_id, item["description"],
                 item.get("owner"), item["priority"], idx),
            )
            created.append(_row_to_action_item(cursor.fetchone()))

    return created


# ── List / edit ────────────────────────────────────────────────────────────

@router.get("/debates/{debate_id}/action-items", response_model=List[ActionItem])
async def list_action_items(debate_id: str, workspace_id: str = Depends(require_auth)):
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        _verify_debate(cursor, debate_id, workspace_id)
        cursor.execute(
            """
            SELECT action_id, material_id, description, owner, priority, status,
                   decision_debate_id, decision, decision_rationale, seq_order
            FROM transcript_action_items
            WHERE debate_id = %s
            ORDER BY seq_order, created_at
            """,
            (debate_id,),
        )
        return [_row_to_action_item(r) for r in cursor.fetchall()]


@router.patch("/debates/{debate_id}/action-items/{action_id}", response_model=ActionItem)
async def update_action_item(
    debate_id: str,
    action_id: str,
    update: ActionItemUpdate,
    workspace_id: str = Depends(require_auth),
):
    fields = []
    params: list = []
    for col in ("description", "owner", "priority", "status"):
        val = getattr(update, col)
        if val is not None:
            fields.append(f"{col} = %s")
            params.append(val)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        _verify_debate(cursor, debate_id, workspace_id)
        params.extend([action_id, debate_id])
        cursor.execute(
            f"""
            UPDATE transcript_action_items SET {', '.join(fields)}
            WHERE action_id = %s AND debate_id = %s
            RETURNING action_id, material_id, description, owner, priority, status,
                      decision_debate_id, decision, decision_rationale, seq_order
            """,
            params,
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action item not found")
        return _row_to_action_item(row)


# ── Decision debate ──────────────────────────────────────────────────────────

def _build_committee(cursor, debate_id: str) -> List[dict]:
    """Reuse up to 3 of the parent debate's participants; fall back to a default pair."""
    cursor.execute(
        "SELECT agent_config FROM participants WHERE debate_id = %s AND participant_type = 'agent' ORDER BY created_at LIMIT 3",
        (debate_id,),
    )
    participants: List[dict] = []
    for row in cursor.fetchall():
        cfg = row["agent_config"] or {}
        name = cfg.get("name")
        if name == "Ultimate Host":
            continue
        if cfg.get("source") == "persistent_agent" and cfg.get("agent_id"):
            participants.append({"agent_id": cfg["agent_id"]})
        elif name and cfg.get("system_prompt") and cfg.get("model_id"):
            participants.append({
                "name": name,
                "role_description": cfg.get("role_description"),
                "system_prompt": cfg["system_prompt"],
                "model_id": cfg["model_id"],
            })

    if not participants:
        participants = [
            {
                "name": "Advisor",
                "role_description": "Pragmatic decision advisor",
                "system_prompt": (
                    "You are a pragmatic advisor on a small panel deciding what to do about a "
                    "single action item. Argue for the most effective, feasible course of action and "
                    "respond to the critic's concerns."
                ),
                "model_id": DEFAULT_MODEL,
            },
            {
                "name": "Critic",
                "role_description": "Risk-focused critic",
                "system_prompt": (
                    "You are a risk-focused critic on a small panel deciding what to do about a "
                    "single action item. Surface risks, trade-offs and alternatives, then converge on "
                    "the soundest decision."
                ),
                "model_id": DEFAULT_MODEL,
            },
        ]
    return participants


@router.post("/debates/{debate_id}/action-items/{action_id}/debate", response_model=DecisionResponse)
async def debate_action_item(
    debate_id: str,
    action_id: str,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    workspace_id: str = Depends(require_auth),
):
    """Spawn a short autonomous panel discussion to decide this action item."""
    if not x_openrouter_key:
        raise HTTPException(status_code=400, detail="OpenRouter API key required (X-OpenRouter-Key)")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        parent = _verify_debate(cursor, debate_id, workspace_id)

        cursor.execute(
            "SELECT description, status, decision_debate_id FROM transcript_action_items WHERE action_id = %s AND debate_id = %s",
            (action_id, debate_id),
        )
        item = cursor.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Action item not found")

        # Idempotent: if a debate is already running/decided, return current state
        if item["decision_debate_id"]:
            return DecisionResponse(
                action_id=action_id,
                status=item["status"],
                decision_debate_id=str(item["decision_debate_id"]),
            )

        committee = _build_committee(cursor, debate_id)
        reasoning_mode = (parent.get("policy_config") or {}).get("reasoning_mode", "medium")

    description = item["description"]
    problem_statement = (
        f"The team must decide what to do about this action item from a meeting:\n\n"
        f'"{description}"\n\n'
        "Debate the best course of action and converge on a clear recommendation."
    )

    # Create the child debate (reuses the standard setup path)
    setup = MeetingSetupService()
    child_debate_id, _participant_ids, _ = setup.create_setup(
        workspace_id=workspace_id,
        title=f"Decision: {description[:80]}",
        problem_statement=problem_statement,
        participants=committee,
        max_rounds=DECISION_MAX_ROUNDS,
        reasoning_mode=reasoning_mode,
    )

    # Mark child running and link it to the action item
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute("UPDATE debates SET state = 'running' WHERE debate_id = %s", (child_debate_id,))
        cursor.execute(
            "UPDATE transcript_action_items SET status = 'debating', decision_debate_id = %s WHERE action_id = %s",
            (child_debate_id, action_id),
        )
        conn.commit()

    # Run it autonomously to conclusion in the background
    await autonomous_service.start_autonomous_debate(
        child_debate_id, x_openrouter_key, DECISION_TURN_DELAY
    )

    return DecisionResponse(
        action_id=action_id,
        status="debating",
        decision_debate_id=child_debate_id,
    )


@router.get("/debates/{debate_id}/action-items/{action_id}/decision", response_model=DecisionResponse)
async def get_action_item_decision(
    debate_id: str,
    action_id: str,
    workspace_id: str = Depends(require_auth),
):
    """Poll the decision; finalizes once the child debate has concluded."""
    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        _verify_debate(cursor, debate_id, workspace_id)
        cursor.execute(
            "SELECT status, decision_debate_id, decision, decision_rationale FROM transcript_action_items WHERE action_id = %s AND debate_id = %s",
            (action_id, debate_id),
        )
        item = cursor.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Action item not found")

        # Already finalized
        if item["status"] == "decided":
            return DecisionResponse(
                action_id=action_id,
                status="decided",
                decision_debate_id=str(item["decision_debate_id"]) if item["decision_debate_id"] else None,
                decision=item["decision"],
                decision_rationale=item["decision_rationale"],
            )

        child_id = item["decision_debate_id"]
        if not child_id:
            return DecisionResponse(action_id=action_id, status=item["status"])

        cursor.execute("SELECT state FROM debates WHERE debate_id = %s", (child_id,))
        child = cursor.fetchone()
        child_ended = bool(child and child["state"] == "ended")

    if not child_ended:
        return DecisionResponse(action_id=action_id, status="debating", decision_debate_id=str(child_id))

    # Child concluded — pull its summary/recommendation and persist the decision
    summary = SummaryService().get_summary(str(child_id))
    decision, rationale = _extract_recommendation(summary)

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            "UPDATE transcript_action_items SET status = 'decided', decision = %s, decision_rationale = %s WHERE action_id = %s",
            (decision, rationale, action_id),
        )
        conn.commit()

    return DecisionResponse(
        action_id=action_id,
        status="decided",
        decision_debate_id=str(child_id),
        decision=decision,
        decision_rationale=rationale,
    )


def _extract_recommendation(summary: Optional[dict]) -> tuple:
    """Pull the panel's recommendation from a debate summary.

    SummaryService encodes the recommendation as a special action_items entry
    (_type == 'recommendation'); fall back to the summary text.
    """
    if not summary:
        return ("No decision was reached.", "")
    for ai in summary.get("action_items") or []:
        if isinstance(ai, dict) and ai.get("_type") == "recommendation":
            desc = ai.get("description", "")
            decision = desc.replace("RECOMMENDATION:", "").strip()
            return (decision or summary.get("summary", ""), "")
    return (summary.get("summary", "Decision reached."), summary.get("minutes", "") or "")
