"""
Agent Memory System - Persistent learning across debates

Anthropic-inspired: Agents that learn and improve over time.
Like Constitutional AI, but the constitution evolves from experience.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
from .database import get_db_connection, get_cursor
import psycopg2.extras


class AgentMemorySystem:
    """
    Manages persistent agent memories across debates
    
    Enables agents to:
    - Remember effective reasoning patterns
    - Learn from successes and failures
    - Build relationships with other agents
    - Develop consistent stances on topics
    """
    
    def __init__(self, workspace_id: str):
        self.workspace_id = workspace_id
    
    def store_memory(
        self,
        agent_role: str,
        memory_type: str,
        content: Dict[str, Any],
        debate_id: str,
        effectiveness: float = 0.5
    ) -> str:
        """
        Store a new memory or update existing one
        
        Args:
            agent_role: "Professional Arguer", "Visionary", etc.
            memory_type: "reasoning_pattern", "stance", "effectiveness", "relationship"
            content: The memory content (JSON)
            debate_id: Debate that contributed this memory
            effectiveness: How effective this was (0-1)
        
        Returns:
            memory_id
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            # Check if similar memory exists
            cursor.execute("""
                SELECT memory_id, debate_ids, confidence, effectiveness, use_count
                FROM agent_memories
                WHERE workspace_id = %s
                  AND agent_role = %s
                  AND memory_type = %s
                  AND content @> %s
                LIMIT 1
            """, (self.workspace_id, agent_role, memory_type, psycopg2.extras.Json(content)))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing memory
                new_debates = list(set(existing['debate_ids'] + [debate_id]))
                new_confidence = min(existing['confidence'] + 0.1, 1.0)
                new_effectiveness = (existing['effectiveness'] + effectiveness) / 2
                
                cursor.execute("""
                    UPDATE agent_memories
                    SET debate_ids = %s::uuid[],
                        confidence = %s,
                        effectiveness = %s,
                        use_count = use_count + 1,
                        updated_at = %s
                    WHERE memory_id = %s
                    RETURNING memory_id
                """, (
                    new_debates,
                    new_confidence,
                    new_effectiveness,
                    datetime.now(timezone.utc),
                    existing['memory_id']
                ))
                
                memory_id = cursor.fetchone()['memory_id']
            else:
                # Create new memory
                memory_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO agent_memories (
                        memory_id, workspace_id, agent_role, memory_type,
                        content, debate_ids, confidence, effectiveness
                    ) VALUES (%s, %s, %s, %s, %s, %s::uuid[], %s, %s)
                    RETURNING memory_id
                """, (
                    memory_id,
                    self.workspace_id,
                    agent_role,
                    memory_type,
                    psycopg2.extras.Json(content),
                    [debate_id],
                    0.5,
                    effectiveness
                ))
            
            cursor.close()
            return memory_id
    
    def recall_memories(
        self,
        agent_role: str,
        memory_type: Optional[str] = None,
        min_confidence: float = 0.5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Recall agent's memories
        
        Args:
            agent_role: Which agent's memories
            memory_type: Filter by type (optional)
            min_confidence: Minimum confidence threshold
            limit: Max memories to return
        
        Returns:
            List of memories, sorted by effectiveness
        """
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            query = """
                SELECT memory_id, memory_type, content, confidence, effectiveness,
                       debate_ids, use_count, created_at, updated_at
                FROM agent_memories
                WHERE workspace_id = %s
                  AND agent_role = %s
                  AND confidence >= %s
            """
            params = [self.workspace_id, agent_role, min_confidence]
            
            if memory_type:
                query += " AND memory_type = %s"
                params.append(memory_type)
            
            query += " ORDER BY effectiveness DESC, confidence DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            memories = cursor.fetchall()
            cursor.close()
            
            return [
                {
                    "memory_id": m['memory_id'],
                    "type": m['memory_type'],
                    "content": m['content'],
                    "confidence": m['confidence'],
                    "effectiveness": m['effectiveness'],
                    "debate_count": len(m['debate_ids']),
                    "use_count": m['use_count']
                }
                for m in memories
            ]
    
    def mark_memory_used(self, memory_id: str):
        """Mark that a memory was used in reasoning"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            cursor.execute("""
                UPDATE agent_memories
                SET use_count = use_count + 1,
                    last_used_at = %s
                WHERE memory_id = %s
            """, (datetime.now(timezone.utc), memory_id))
            cursor.close()
    
    def get_agent_stats(self, agent_role: str) -> Dict[str, Any]:
        """Get statistics about agent's learned memories"""
        with get_db_connection() as conn:
            cursor = get_cursor(conn)
            
            cursor.execute("""
                SELECT
                    COUNT(*) as total_memories,
                    AVG(confidence) as avg_confidence,
                    AVG(effectiveness) as avg_effectiveness,
                    SUM(use_count) as total_uses,
                    COUNT(DISTINCT unnest(debate_ids)) as debates_learned_from
                FROM agent_memories
                WHERE workspace_id = %s AND agent_role = %s
            """, (self.workspace_id, agent_role))
            
            stats = cursor.fetchone()
            cursor.close()
            
            return {
                "agent_role": agent_role,
                "total_memories": stats['total_memories'] or 0,
                "avg_confidence": round(float(stats['avg_confidence'] or 0), 2),
                "avg_effectiveness": round(float(stats['avg_effectiveness'] or 0), 2),
                "total_uses": stats['total_uses'] or 0,
                "debates_learned_from": stats['debates_learned_from'] or 0
            }
