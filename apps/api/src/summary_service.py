"""PeerForge — Peer-Review Report generation service (replaces old meeting summary)"""
import uuid
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import psycopg2.extras
from .database import get_db_connection, get_cursor
from .openrouter_client import OpenRouterClient


class SummaryService:
    """
    Service for generating and storing peer-review reports.

    The generated report includes:
    - Summary of Contribution (1-3 sentences)
    - Detailed Review Notes (strengths, weaknesses, methodology, literature)
    - Action Items / Required Changes (structured list with owner + priority)
    - Recommendation: Accept / Minor Revision / Major Revision / Reject
    """
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None):
        self.client = openrouter_client
    
    def generate_summary(
        self,
        debate_id: str,
        openrouter_api_key: str,
        model_id: str = "anthropic/claude-sonnet-4-5"
    ) -> Dict[str, Any]:
        """
        Generate summary/minutes/action items for a debate
        
        Args:
            debate_id: Debate UUID
            openrouter_api_key: OpenRouter BYOK key (never stored)
            model_id: Model to use for generation
        
        Returns:
            Dict with summary, minutes, action_items
        
        Raises:
            ValueError: Debate not found or not ended
            RuntimeError: OpenRouter error
        """
        # Get debate and events
        debate = self._get_debate(debate_id)
        if not debate:
            raise ValueError(f"Debate {debate_id} not found")
        
        if debate['state'] != 'ended':
            raise ValueError(f"Debate must be ended to generate summary (current state: {debate['state']})")
        
        events = self._get_events(debate_id)
        
        # Build context from events
        context = self._build_context(debate, events)
        
        # Generate via OpenRouter
        client = self.client or OpenRouterClient(api_key=openrouter_api_key)
        
        prompt = self._build_summary_prompt(context)
        response = client.chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
            _debate_id=debate_id,
            _stage="summary",
        )

        # Parse and validate structured output — raises RuntimeError if unparseable
        outputs = self._parse_summary_response(response['content'])

        # Final validation: ensure outputs round-trip as valid JSON before storage
        try:
            _probe = json.dumps(outputs)
            json.loads(_probe)  # verify
        except (TypeError, ValueError) as _ve:
            raise RuntimeError(f"Generated summary failed JSON validation: {_ve}") from _ve

        # Store in database
        self._save_outputs(
            debate_id=debate_id,
            summary=outputs['summary'],
            minutes=outputs['minutes'],
            action_items=outputs['action_items'],
            recommendation=outputs.get('recommendation', ''),
            recommendation_rationale=outputs.get('recommendation_rationale', ''),
            model_used=model_id,
            token_count=response.get('usage', {}).get('total_tokens'),
        )

        # Create event in ledger
        self._create_summary_event(debate_id, outputs)

        # ── Eval log: record summary ───────────────────────────────────
        try:
            from .services.eval_logger import get_logger
            get_logger(debate_id).log_summary(
                model=model_id,
                request_prompt=prompt,
                summary=outputs.get('summary', ''),
                minutes=outputs.get('minutes', ''),
                action_items=outputs.get('action_items', []),
                usage=response.get('usage', {}),
            )
        except Exception as _log_exc:
            print(f"[eval_logger] log_summary failed: {_log_exc}")
        # ─────────────────────────────────────────────────────────────

        return outputs
    
    def get_summary(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """
        Get existing summary for a debate
        
        Returns:
            Dict with summary/minutes/action_items or None if not generated
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT 
                    output_id, debate_id, summary, minutes, action_items,
                    generated_at, model_used, token_count, created_at
                FROM debate_outputs
                WHERE debate_id = %s
            """, (debate_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _get_debate(self, debate_id: str) -> Optional[Dict[str, Any]]:
        """Get debate details"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT debate_id, workspace_id, title, description, state, created_at
                FROM debates
                WHERE debate_id = %s
            """, (debate_id,))
            
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def _get_events(self, debate_id: str) -> List[Dict[str, Any]]:
        """Get all events for debate"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT 
                    event_id, event_type, sender_type, sequence_number,
                    content, created_at
                FROM events
                WHERE debate_id = %s
                ORDER BY sequence_number ASC
            """, (debate_id,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def _build_context(self, debate: Dict[str, Any], events: List[Dict[str, Any]]) -> str:
        """Build context string from review session events."""
        lines = [
            f"# Research Title: {debate['title']}",
            f"Research Question / Abstract: {debate.get('description', 'N/A')}",
            "",
            "## Review Session Transcript:",
            "",
        ]

        for event in events:
            event_type = event['event_type']
            content = event.get('content', {})

            if event_type == 'system_message':
                action = content.get('action', 'unknown')
                lines.append(f"[System: {action}]")
            elif event_type == 'intervention':
                text = content.get('text', '')
                tagged = content.get('tagged_agents', [])
                lines.append(f"[Researcher/Moderator: {text} (directed at: {', '.join(tagged)})]")
            elif event_type in ['agent_message', 'debate_turn']:
                agent = content.get('agent_name', event.get('sender_type', 'Reviewer'))
                text = content.get('text', content.get('message', ''))
                is_chair = content.get('is_host_conclusion', False)
                prefix = "[Review Chair Final]" if is_chair else f"[{agent}]"
                lines.append(f"{prefix}: {text[:400]}{'...' if len(text) > 400 else ''}")

        return "\n".join(lines)
    
    def _build_summary_prompt(self, context: str) -> str:
        """Build prompt for peer-review report generation."""
        return f"""You are a senior academic editor synthesising a peer-review session into a structured report.

{context}

CRITICAL: Output ONLY valid, complete JSON. No markdown, no code blocks, no explanations.

Output EXACTLY this JSON structure:

{{
  "summary": "1-3 sentence summary of the research contribution and overall panel verdict",
  "minutes": "Comprehensive peer-review notes covering: (1) Contribution & Novelty assessment, (2) Key Strengths identified by reviewers, (3) Weaknesses & Methodological Concerns raised, (4) Literature & Related-Work Gaps, (5) Reproducibility and Ethics observations. 3-6 paragraphs. Cite specific reviewer positions.",
  "action_items": [
    {{"description": "Required change or suggested experiment", "owner": "Responsible reviewer role or 'Authors'", "priority": "high"}},
    {{"description": "Another required change", "owner": "Authors", "priority": "medium"}}
  ],
  "recommendation": "Accept | Minor Revision | Major Revision | Reject",
  "recommendation_rationale": "2-3 sentences explaining the recommendation with reference to the key reviewer arguments"
}}

Requirements:
- summary: Capture the paper's main contribution and the panel's dominant verdict
- minutes: Be specific — name methodological issues, missing citations, and strong points as raised by reviewers
- action_items: Specific, actionable changes for the authors (not vague suggestions)
- recommendation: Choose EXACTLY ONE of: Accept / Minor Revision / Major Revision / Reject
- recommendation_rationale: Must cite specific reviewer concerns that drove the recommendation
- MUST be valid complete JSON — close all quotes, brackets, braces

START WITH {{ AND END WITH }}"""
    
    def _parse_summary_response(self, content: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured outputs.

        Strategies (applied in order):
          1. Strip markdown fences, then direct JSON parse
          2. Extract JSON object from anywhere in the text (first {...})
          3. Structural repair: close unclosed brackets/braces
          4. Targeted key extraction as last resort
          5. Reject and raise RuntimeError — do NOT store garbage

        The returned dict is always valid and contains all required keys.
        """
        import re

        REQUIRED = ['summary', 'minutes', 'action_items']

        def _extract(parsed: dict) -> dict:
            return {
                'summary': parsed.get('summary', ''),
                'minutes': parsed.get('minutes', ''),
                'action_items': parsed.get('action_items', []),
                'recommendation': parsed.get('recommendation', ''),
                'recommendation_rationale': parsed.get('recommendation_rationale', ''),
            }

        def _has_required(parsed: dict) -> bool:
            return all(k in parsed for k in REQUIRED)

        def _strip_fences(text: str) -> str:
            """Remove leading/trailing markdown code fences."""
            text = text.strip()
            text = re.sub(r'^```(?:json)?\s*\n?', '', text)
            text = re.sub(r'\n?```\s*$', '', text)
            return text.strip()

        def _repair(text: str) -> str:
            """Close unclosed JSON brackets and braces."""
            # Remove trailing commas before closing delimiters
            text = re.sub(r',\s*([}\]])', r'\1', text)
            # Balance braces and brackets
            open_braces = text.count('{') - text.count('}')
            open_brackets = text.count('[') - text.count(']')
            if open_brackets > 0:
                text = text.rstrip().rstrip(',') + ']' * open_brackets
            if open_braces > 0:
                text = text.rstrip().rstrip(',') + '}' * open_braces
            return text

        # ── Strategy 1: strip fences, then parse ────────────────────────
        try:
            candidate = _strip_fences(content)
            parsed = json.loads(candidate)
            if _has_required(parsed):
                return _extract(parsed)
            print(f"[summary] JSON parsed but missing required keys: {list(parsed.keys())}")
        except json.JSONDecodeError as exc:
            print(f"[summary] Strategy 1 (strip+parse) failed: {exc}")

        # ── Strategy 2: extract first {...} block ────────────────────────
        try:
            match = re.search(r'\{[\s\S]+\}', content)
            if match:
                parsed = json.loads(match.group(0))
                if _has_required(parsed):
                    return _extract(parsed)
        except json.JSONDecodeError as exc:
            print(f"[summary] Strategy 2 (extract block) failed: {exc}")

        # ── Strategy 3: repair + parse ───────────────────────────────────
        try:
            candidate = _strip_fences(content)
            if candidate.startswith('{'):
                repaired = _repair(candidate)
                parsed = json.loads(repaired)
                if _has_required(parsed):
                    print("[summary] Strategy 3 (repair) succeeded")
                    return _extract(parsed)
        except Exception as exc:
            print(f"[summary] Strategy 3 (repair) failed: {exc}")

        # ── Strategy 4: targeted key extraction ─────────────────────────
        # Pull individual string values for each required key
        def _pull_value(key: str, text: str) -> str:
            pattern = rf'"{key}"\s*:\s*"((?:[^"\\]|\\.)*)"'
            m = re.search(pattern, text, re.DOTALL)
            return m.group(1) if m else ''

        summary_val = _pull_value('summary', content)
        minutes_val = _pull_value('minutes', content)
        if summary_val and minutes_val:
            print("[summary] Strategy 4 (key extraction) partially succeeded")
            return {
                'summary': summary_val,
                'minutes': minutes_val,
                'action_items': [],
                'recommendation': _pull_value('recommendation', content),
                'recommendation_rationale': _pull_value('recommendation_rationale', content),
            }

        # ── All strategies failed — raise to prevent storing garbage ────
        raise RuntimeError(
            f"Summary generation produced non-JSON output that could not be repaired. "
            f"Raw response (first 300 chars): {content[:300]!r}"
        )
    
    def _save_outputs(
        self,
        debate_id: str,
        summary: str,
        minutes: str,
        action_items: List[Dict[str, Any]],
        model_used: str,
        token_count: Optional[int],
        recommendation: str = '',
        recommendation_rationale: str = '',
    ) -> None:
        """Save peer-review report outputs to debate_outputs table."""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            # Encode recommendation into action_items metadata for backward compat
            meta_items = action_items or []
            if recommendation:
                meta_items = list(meta_items) + [{
                    "description": f"RECOMMENDATION: {recommendation}. {recommendation_rationale}",
                    "owner": "Review Chair",
                    "priority": "high",
                    "_type": "recommendation",
                }]
            cursor.execute("""
                INSERT INTO debate_outputs (
                    debate_id, summary, minutes, action_items,
                    generated_at, model_used, token_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (debate_id)
                DO UPDATE SET
                    summary = EXCLUDED.summary,
                    minutes = EXCLUDED.minutes,
                    action_items = EXCLUDED.action_items,
                    generated_at = EXCLUDED.generated_at,
                    model_used = EXCLUDED.model_used,
                    token_count = EXCLUDED.token_count,
                    updated_at = NOW()
            """, (
                debate_id,
                summary,
                minutes,
                psycopg2.extras.Json(meta_items),
                datetime.now(timezone.utc),
                model_used,
                token_count,
            ))
    
    def _create_summary_event(self, debate_id: str, outputs: Dict[str, Any]) -> None:
        """Create debate_summary event in events ledger"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Get next sequence number
            cursor.execute("""
                SELECT COALESCE(MAX(sequence_number), 0) + 1 AS next_seq
                FROM events
                WHERE debate_id = %s
            """, (debate_id,))
            next_seq = cursor.fetchone()['next_seq']
            
            # Create event
            event_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO events (
                    event_id, debate_id, event_type, sender_type,
                    sequence_number, content, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                event_id,
                debate_id,
                'debate_summary',
                'system',
                next_seq,
                psycopg2.extras.Json({
                    'summary': outputs['summary'],
                    'action_item_count': len(outputs['action_items'])
                }),
                datetime.now(timezone.utc)
            ))
