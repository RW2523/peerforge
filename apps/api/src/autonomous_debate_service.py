"""
Autonomous Debate Service - Handles self-running YOLO debates
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from .database import get_db_connection, get_cursor
from .turn_orchestrator import TurnOrchestrator
from .summary_service import SummaryService
import logging

logger = logging.getLogger(__name__)

# Termination bounds. Every autonomous turn issues paid LLM calls, so the loop
# must terminate even when a debate was created with no policy at all.
DEFAULT_MAX_ROUNDS = 5
MAX_TURNS_HARD_CEILING = 200
MAX_CONSECUTIVE_FAILURES = 3


class AutonomousDebateService:
    """Manages autonomous debate execution"""
    
    def __init__(self):
        self.running_debates: Dict[str, asyncio.Task] = {}
    
    async def start_autonomous_debate(
        self,
        debate_id: str,
        openrouter_api_key: str,
        auto_turn_delay: int = 10
    ) -> Dict[str, Any]:
        """Start autonomous debate execution"""
        
        # Update debate status
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates 
                SET autonomous_mode = true,
                    autonomous_status = 'running',
                    auto_turn_delay_seconds = %s,
                    started_at = COALESCE(started_at, NOW())
                WHERE debate_id = %s
            """, (auto_turn_delay, debate_id))
            conn.commit()
            cursor.close()
        
        # Start background task
        task = asyncio.create_task(
            self._run_autonomous_loop(debate_id, openrouter_api_key, auto_turn_delay)
        )
        self.running_debates[debate_id] = task
        
        return {"status": "running", "debate_id": debate_id}
    
    async def pause_autonomous_debate(self, debate_id: str):
        """Pause autonomous debate"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates 
                SET autonomous_status = 'paused'
                WHERE debate_id = %s
            """, (debate_id,))
            conn.commit()
            cursor.close()
    
    async def resume_autonomous_debate(self, debate_id: str, openrouter_api_key: str):
        """Resume autonomous debate - restart background task if needed"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates 
                SET autonomous_status = 'running'
                WHERE debate_id = %s
            """, (debate_id,))
            conn.commit()
            
            # Get the debate config to restart the loop if needed
            cursor.execute("""
                SELECT auto_turn_delay_seconds FROM debates WHERE debate_id = %s
            """, (debate_id,))
            result = cursor.fetchone()
            cursor.close()
        
        # Restart background task if not already running
        if debate_id not in self.running_debates and result:
            auto_turn_delay = result.get('auto_turn_delay_seconds', 10)
            logger.info(f"🔄 Restarting autonomous loop for debate {debate_id}")
            task = asyncio.create_task(
                self._run_autonomous_loop(debate_id, openrouter_api_key, auto_turn_delay)
            )
            self.running_debates[debate_id] = task
            logger.info(f"✅ Autonomous loop restarted")
    
    async def _run_autonomous_loop(
        self,
        debate_id: str,
        openrouter_api_key: str,
        delay_seconds: int
    ):
        """Main autonomous execution loop"""
        orchestrator = TurnOrchestrator(openrouter_api_key)
        consecutive_failures = 0

        try:
            while True:
                # Check status
                status = self._get_debate_status(debate_id)
                
                if status == 'paused':
                    await asyncio.sleep(2)
                    continue
                
                if status != 'running':
                    break
                
                # Check if debate should end
                if self._should_end_debate(debate_id):
                    await self._conclude_debate(debate_id, openrouter_api_key)
                    break
                
                # Trigger next turn
                try:
                    result = orchestrator.trigger_next_turn(debate_id)
                    logger.info(f"🤖 Auto-turn completed: {result.get('agent_name')}")
                    consecutive_failures = 0
                except Exception as e:
                    consecutive_failures += 1
                    logger.error(f"❌ Auto-turn failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {e}")
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        # A provider outage or a misconfigured debate would
                        # otherwise retry forever, paying for each attempt.
                        logger.error(f"⛔ Pausing {debate_id} after {consecutive_failures} consecutive failures")
                        self._set_status(debate_id, 'paused')
                        break
                    await asyncio.sleep(delay_seconds * consecutive_failures)
                    continue
                
                # Wait before next turn
                await asyncio.sleep(delay_seconds)
                
        except Exception as e:
            logger.error(f"❌ Autonomous loop crashed: {e}")
            self._set_status(debate_id, 'paused')
        finally:
            if debate_id in self.running_debates:
                del self.running_debates[debate_id]
    
    def _get_debate_status(self, debate_id: str) -> Optional[str]:
        """Get current autonomous status"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT autonomous_status, state
                FROM debates WHERE debate_id = %s
            """, (debate_id,))
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                return None
            
            # If debate ended manually, stop autonomous
            if result['state'] == 'ended':
                return 'completed'
            
            return result['autonomous_status']
    
    def _should_end_debate(self, debate_id: str) -> bool:
        """Check if debate should conclude"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT 
                    policy_config,
                    started_at,
                    (SELECT COUNT(*) FROM events 
                     WHERE debate_id = %s AND event_type = 'agent_message') as turn_count
                FROM debates WHERE debate_id = %s
            """, (debate_id, debate_id))
            result = cursor.fetchone()
            cursor.close()
            
            if not result:
                logger.warning(f"⚠️ No debate found for {debate_id}")
                return True
            
            policy = result['policy_config'] or {}
            turn_count = result['turn_count']
            
            # Get participant count for round calculation
            cursor = get_cursor(conn)
            cursor.execute("""
                SELECT COUNT(*) as count FROM participants WHERE debate_id = %s
            """, (debate_id,))
            participant_count = cursor.fetchone()['count']
            cursor.close()
            
            # Absolute ceiling: even a misconfigured policy cannot spend without
            # bound, because every turn issues paid LLM calls.
            if turn_count >= MAX_TURNS_HARD_CEILING:
                logger.error(f"⛔ Ending due to hard turn ceiling: {turn_count} >= {MAX_TURNS_HARD_CEILING}")
                return True

            # Check max_rounds. Falls back to a default so that a debate created
            # without max_rounds or timebox_minutes still terminates.
            max_rounds = policy.get('max_rounds') or DEFAULT_MAX_ROUNDS
            if max_rounds and participant_count > 0:
                current_round = (turn_count // participant_count) + 1
                logger.debug(f"📊 Round check: {current_round}/{max_rounds} (turns={turn_count}, participants={participant_count})")
                if current_round > max_rounds:
                    logger.error(f"⛔ Ending due to max_rounds: {current_round} > {max_rounds}")
                    return True
            
            # Check timebox
            timebox_minutes = policy.get('timebox_minutes')
            if timebox_minutes and result['started_at']:
                now = datetime.now(timezone.utc)
                started = result['started_at']
                # Make started_at timezone-aware if it isn't already
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                elapsed = (now - started).total_seconds() / 60
                logger.info(f"⏱️ Timebox check: {elapsed:.1f}/{timebox_minutes} minutes")
                if elapsed >= timebox_minutes:
                    logger.error(f"⛔ Ending due to timebox: {elapsed:.1f} >= {timebox_minutes}")
                    return True
            
            logger.info(f"✅ Debate should continue")
            return False
    
    async def _conclude_debate(self, debate_id: str, openrouter_api_key: str):
        """Mark as completed, then generate the summary.

        The session must be ended BEFORE summarising — SummaryService refuses
        to summarise a running debate, so the old order silently produced
        auto-mode sessions without summaries.
        """
        logger.info(f"🏁 Auto-concluding debate: {debate_id}")

        # Update status first
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates
                SET autonomous_status = 'completed',
                    state = 'ended',
                    ended_at = NOW()
                WHERE debate_id = %s
            """, (debate_id,))
            conn.commit()
            cursor.close()

        # Generate summary now that the debate is ended
        summary_service = SummaryService()
        try:
            summary = summary_service.generate_summary(
                debate_id=debate_id,
                openrouter_api_key=openrouter_api_key
            )
            logger.info(f"📄 Summary generated: {len(summary.get('summary', ''))} chars")
        except Exception as e:
            logger.error(f"⚠️ Summary generation failed: {e}")

        logger.info(f"✅ Debate concluded: {debate_id}")
    
    def _set_status(self, debate_id: str, status: str):
        """Set autonomous status"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE debates 
                SET autonomous_status = %s
                WHERE debate_id = %s
            """, (status, debate_id))
            conn.commit()
            cursor.close()


# Global instance
autonomous_service = AutonomousDebateService()
