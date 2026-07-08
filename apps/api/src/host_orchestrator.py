"""Host conclusion orchestration - separate from regular turn flow"""
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
import psycopg2.extras
from .database import get_db_connection, get_cursor
from .openrouter_client import OpenRouterClient


class HostOrchestrator:
    """
    Manages the Review Chair conclusion flow

    The chair is NOT a regular participant - it only speaks at the end
    to provide a neutral, evidence-based synthesis of all reviewer positions
    and a final peer-review recommendation.
    """
    
    def __init__(self, openrouter_api_key: str):
        self.openrouter_client = OpenRouterClient(openrouter_api_key)
    
    def trigger_conclusion(self, debate_id: str) -> Dict[str, Any]:
        """
        Trigger the Review Chair to provide the final peer-review conclusion.

        Only called after all regular reviewer rounds are complete.
        The chair synthesises all reviewer positions into a structured recommendation.

        Returns:
            Dict with event_id, message, etc.
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Get debate details
            cursor.execute("""
                SELECT debate_id, title, description, state, policy_config
                FROM debates
                WHERE debate_id = %s
            """, (debate_id,))
            
            debate = cursor.fetchone()
            if not debate:
                raise ValueError(f"Debate {debate_id} not found")
            
            if debate['state'] != 'running':
                raise ValueError(f"Debate must be in 'running' state")
            
            policy_config = debate['policy_config'] or {}
            
            # Verify host is enabled
            if not policy_config.get('enable_host'):
                raise ValueError("Host is not enabled for this debate")
            
            # Idempotent: if the chair already concluded, return the existing
            # conclusion instead of erroring — the user's intent (wrap up) is
            # already satisfied, and re-clicking Conclude shouldn't fail.
            if policy_config.get('host_concluded'):
                cursor.execute("""
                    SELECT event_id, sequence_number, content
                    FROM events
                    WHERE debate_id = %s AND event_type = 'agent_message'
                      AND content->>'is_host_conclusion' = 'true'
                    ORDER BY sequence_number DESC
                    LIMIT 1
                """, (debate_id,))
                existing = cursor.fetchone()
                if existing:
                    content = existing['content'] or {}
                    return {
                        'event_id': str(existing['event_id']),
                        'message': content.get('text', ''),
                        'participant_name': 'Review Chair',
                        'sequence_number': existing['sequence_number'],
                        'is_conclusion': True,
                        'already_concluded': True,
                    }
                # Flag set but no stored conclusion — fall through and regenerate.
            
            # Get host model
            host_model_id = policy_config.get('host_model_id', 'openai/gpt-4o-mini')
            
            # Get all participants for @mention list
            cursor.execute("""
                SELECT participant_id, agent_config, role_name
                FROM participants
                WHERE debate_id = %s
                ORDER BY created_at ASC
            """, (debate_id,))
            
            participants = cursor.fetchall()
            participant_names = [
                (p['agent_config'] or {}).get('name') or p['role_name']
                for p in participants
            ]
            
            # Get full debate history
            cursor.execute("""
                SELECT event_type, sender_type, content, created_at
                FROM events
                WHERE debate_id = %s
                ORDER BY sequence_number ASC
            """, (debate_id,))
            
            history_events = cursor.fetchall()
            
            # Build host system prompt from template
            from .agent_templates import get_template_by_id
            host_template = get_template_by_id('review-chair')
            if not host_template:
                raise ValueError("Review Chair template not found")
            
            host_system_prompt = host_template['system_prompt']
            
            # Build conversation summary for host
            conversation_summary = self._build_host_context(
                debate['title'],
                policy_config.get('desired_outcomes', []),
                participant_names,
                history_events
            )
            
            # Call LLM for host conclusion
            messages = [
                {"role": "system", "content": host_system_prompt},
                {"role": "user", "content": conversation_summary}
            ]
            
            host_response = self.openrouter_client.chat_completion(
                model=host_model_id,
                messages=messages,
                temperature=0.3,  # Low temperature for consistency
                max_tokens=3000
            )
            
            # Persist host conclusion as event
            event_id = str(uuid.uuid4())
            total_turns = policy_config.get('total_turns_taken', 0)
            
            cursor.execute("""
                SELECT COALESCE(MAX(sequence_number), 0) + 1 as next_seq
                FROM events
                WHERE debate_id = %s
            """, (debate_id,))
            next_seq = cursor.fetchone()['next_seq']
            
            cursor.execute("""
                INSERT INTO events (
                    event_id, debate_id, event_type, sender_type, sender_id,
                    sequence_number, content, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, NOW()
                )
                RETURNING event_id, sequence_number
            """, (
                event_id,
                debate_id,
                'agent_message',
                'system',  # Host is system-type
                None,  # No specific participant_id for host
                next_seq,
                psycopg2.extras.Json({
                    'agent_name': 'Review Chair',
                    'text': host_response['content'],
                    'model': host_response.get('model', host_model_id),
                    'is_host_conclusion': True
                })
            ))
            
            # Update policy config - mark as concluded
            policy_config['host_concluded'] = True
            policy_config['total_turns_taken'] = total_turns  # Don't increment for host
            
            cursor.execute("""
                UPDATE debates
                SET policy_config = %s, updated_at = NOW()
                WHERE debate_id = %s
            """, (psycopg2.extras.Json(policy_config), debate_id))
            
            return {
                'event_id': event_id,
                'message': host_response['content'],
                'participant_name': 'Review Chair',
                'sequence_number': next_seq,
                'is_conclusion': True
            }
    
    def _build_host_context(
        self,
        title: str,
        desired_outcomes: List[str],
        participant_names: List[str],
        events: List[Dict[str, Any]]
    ) -> str:
        """Build context summary for host to analyze"""
        
        # Extract all agent messages
        agent_messages = []
        for event in events:
            if event['event_type'] == 'agent_message':
                content = event.get('content') or {}
                agent_name = content.get('agent_name', 'Agent')
                text = content.get('text', '')
                agent_messages.append(f"**{agent_name}**: {text}\n")
        
        conversation_text = "\n".join(agent_messages)
        
        participant_list = ", ".join([f"@{name}" for name in participant_names])
        outcomes_text = "\n".join([f"- {outcome}" for outcome in desired_outcomes]) if desired_outcomes else "- Reach a clear decision"
        
        # Get current date/time for temporal context
        current_datetime = datetime.now(timezone.utc)
        current_date_str = current_datetime.strftime("%A, %B %d, %Y")
        current_time_str = current_datetime.strftime("%I:%M %p UTC")
        
        prompt = f"""You are the Review Chair delivering the final structured peer-review conclusion.

**Current Date**: {current_date_str} at {current_time_str}

**Research Title**: {title}

**Reviewers**: {participant_list}

**Review Objectives**:
{outcomes_text}

**Full Review Session Transcript**:
{conversation_text}

---

**Your Task — Structured Peer-Review Report**:
Synthesise the panel's positions into a definitive peer-review report with the following sections:

1. **Summary of Contribution** — What does this work claim to contribute and what is its scope?
2. **Key Strengths** — The strongest positives identified across all reviewers (with citations to reviewer arguments).
3. **Key Weaknesses & Methodology Concerns** — The most critical issues raised.
4. **Literature & Related-Work Gaps** — Missing citations or inadequate engagement with prior work.
5. **Reproducibility & Ethics** — Data/code availability, ethical concerns, limitations transparency.
6. **Required Changes** — Specific, actionable revisions the authors must address.
7. **Recommendation** — Choose exactly one: Accept / Minor Revision / Major Revision / Reject — with explicit rationale.

Be objective, cite specific reviewer arguments, and acknowledge where the panel disagreed."""
        
        return prompt
