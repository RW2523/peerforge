"""
Analytics API Routes - Novel features endpoints

All endpoints are additive, non-breaking. Feature-flagged for gradual rollout.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import os

from ..debate_progress_tracker import DebateProgressTracker
from ..strategic_host_agent import StrategicHostAgent
from ..agent_memory_system import AgentMemorySystem
from ..evidence_grounding import EvidenceGroundingValidator

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Feature flags
ENABLE_PROGRESS_TRACKING = os.getenv('ENABLE_PROGRESS_TRACKING', 'true').lower() == 'true'
ENABLE_AGENT_MEMORY = os.getenv('ENABLE_AGENT_MEMORY', 'true').lower() == 'true'
ENABLE_EVIDENCE_GROUNDING = os.getenv('ENABLE_EVIDENCE_GROUNDING', 'true').lower() == 'true'
ENABLE_STRATEGIC_HOST = os.getenv('ENABLE_STRATEGIC_HOST', 'true').lower() == 'true'


@router.get("/debates/{debate_id}/progress")
async def get_debate_progress(debate_id: str):
    """
    Get real-time debate progress metrics
    
    Returns:
        - coverage_score: How many desired outcomes covered (0-1)
        - depth_score: How deeply explored (0-1)
        - new_info_rate: % of recent messages adding new info (0-1)
        - consensus_level: Agreement level (0-1)
        - polarization: Disagreement level (0-1)
        - health: "poor/fair/good/excellent"
        - action_items: Actionable recommendations
    """
    if not ENABLE_PROGRESS_TRACKING:
        raise HTTPException(status_code=501, detail="Progress tracking not enabled")
    
    try:
        tracker = DebateProgressTracker(debate_id)
        progress = tracker.analyze()
        return {
            "success": True,
            "debate_id": debate_id,
            "progress": progress
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze progress: {str(e)}")


@router.get("/debates/{debate_id}/host-decision")
async def get_host_intervention_decision(debate_id: str):
    """
    Check if strategic host should intervene
    
    Returns:
        - should_intervene: bool
        - action: "redirect", "conclude", "seek_common_ground", etc.
        - message: What host would say
        - urgency: "low/medium/high"
        - reason: Why this decision was made
    """
    if not ENABLE_STRATEGIC_HOST:
        raise HTTPException(status_code=501, detail="Strategic host not enabled")
    
    try:
        host = StrategicHostAgent(debate_id)
        decision = host.should_intervene()
        return {
            "success": True,
            "debate_id": debate_id,
            "decision": decision
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check host decision: {str(e)}")


@router.get("/agents/{agent_role}/memories")
async def get_agent_memories(
    agent_role: str,
    workspace_id: str = Query(..., description="Workspace ID"),
    memory_type: Optional[str] = Query(None, description="Filter by memory type"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Get agent's learned memories
    
    Returns list of memories with effectiveness scores
    """
    if not ENABLE_AGENT_MEMORY:
        raise HTTPException(status_code=501, detail="Agent memory not enabled")
    
    try:
        memory_system = AgentMemorySystem(workspace_id)
        memories = memory_system.recall_memories(
            agent_role=agent_role,
            memory_type=memory_type,
            limit=limit
        )
        return {
            "success": True,
            "agent_role": agent_role,
            "memories": memories,
            "count": len(memories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to recall memories: {str(e)}")


@router.get("/agents/{agent_role}/stats")
async def get_agent_statistics(
    agent_role: str,
    workspace_id: str = Query(..., description="Workspace ID")
):
    """
    Get agent's learning statistics
    
    Returns:
        - total_memories: How many memories stored
        - avg_confidence: Average confidence in memories
        - avg_effectiveness: How effective learned patterns are
        - debates_learned_from: Number of debates contributed to learning
    """
    if not ENABLE_AGENT_MEMORY:
        raise HTTPException(status_code=501, detail="Agent memory not enabled")
    
    try:
        memory_system = AgentMemorySystem(workspace_id)
        stats = memory_system.get_agent_stats(agent_role)
        return {
            "success": True,
            **stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/validate/evidence")
async def validate_evidence_grounding(
    message: str,
    agent_name: str
):
    """
    Validate that a message has properly grounded factual claims
    
    Used during message generation to check for unsubstantiated facts
    
    Returns:
        - valid: bool
        - violations: List of ungrounded claims
        - grounding_rate: % of claims that are grounded
    """
    if not ENABLE_EVIDENCE_GROUNDING:
        raise HTTPException(status_code=501, detail="Evidence grounding not enabled")
    
    try:
        validator = EvidenceGroundingValidator()
        result = validator.validate(message, agent_name)
        return {
            "success": True,
            "agent_name": agent_name,
            **result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate evidence: {str(e)}")


@router.get("/health")
async def analytics_health():
    """Health check for analytics features"""
    return {
        "status": "healthy",
        "features": {
            "progress_tracking": ENABLE_PROGRESS_TRACKING,
            "agent_memory": ENABLE_AGENT_MEMORY,
            "evidence_grounding": ENABLE_EVIDENCE_GROUNDING,
            "strategic_host": ENABLE_STRATEGIC_HOST
        }
    }
