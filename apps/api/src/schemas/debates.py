"""Pydantic models for debate-related endpoints"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from .agents import AgentInput


class DebateRunRequest(BaseModel):
    """Request to run a debate"""
    problem_statement: str = Field(..., description="Problem to discuss")
    agents: List[AgentInput] = Field(..., description="Exactly 3 agents for M1")
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter API key (BYOK); falls back to the server key"
    )
    debate_title: str = Field(default="Untitled Debate", description="Optional debate title")


class DebateRunResponse(BaseModel):
    """Response from debate run"""
    debate_id: str
    status: str
    outputs: Dict[str, Any]
    event_history: List[Dict[str, Any]]


class CreateDebateRequest(BaseModel):
    """Request to create a debate"""
    workspace_id: str = Field(..., description="Workspace ID")
    # Bounded here so an over-long title is a readable 422 rather than a
    # Postgres truncation error surfaced to the screen as a 500.
    title: str = Field(..., min_length=1, max_length=500, description="Debate title")
    # Accepted at the top level because that is how every caller sends it —
    # the API silently dropped it (pydantic ignores unknown fields), while
    # everything downstream reads policy_config['problem_statement']. The
    # result: 0 of 99 live sessions had a problem statement unless they came
    # through conversational setup, so preflight skipped web research, the
    # retrieval query fell back to "context summary", and reviewers were shown
    # "Problem: N/A". The route folds this into policy_config, which stays the
    # canonical location.
    problem_statement: Optional[str] = Field(
        default=None, max_length=10000,
        description="The research problem the panel is reviewing",
    )
    policy_config: Optional[Dict[str, Any]] = Field(default=None, description="Policy configuration")


class ParticipantInfo(BaseModel):
    """Participant information"""
    participant_id: str
    participant_type: str
    role_name: str
    agent_config: Optional[Dict[str, Any]] = None
    created_at: str


class DebateResponse(BaseModel):
    """Debate response"""
    debate_id: str
    workspace_id: str
    title: str
    state: str
    policy_config: Optional[Dict[str, Any]] = Field(default=None, description="Policy configuration (rounds, time limits, etc.)")
    created_at: str
    participants: List[ParticipantInfo] = Field(default_factory=list, description="Debate participants")
    autonomous_mode: Optional[bool] = Field(default=False, description="Whether autonomous/YOLO mode is enabled")
    autonomous_status: Optional[str] = Field(default=None, description="Autonomous debate status (running/paused/completed)")
    auto_turn_delay_seconds: Optional[int] = Field(default=10, description="Delay between autonomous turns in seconds")


class InterveneRequest(BaseModel):
    """Request to intervene in debate"""
    message: str = Field(..., description="Intervention message", min_length=1)
    tagged_agents: Optional[List[str]] = Field(default=None, description="Agent names to tag")


class InterventionResponse(BaseModel):
    """Response from intervention"""
    event_id: str
    debate_id: str
    message: str
    tagged_agents: List[str]


class DebateListItem(BaseModel):
    """Single debate item in list"""
    debate_id: str
    workspace_id: str
    title: str
    state: str
    created_at: str
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class DebateListResponse(BaseModel):
    """Response for listing debates"""
    items: List[DebateListItem]
    next_cursor: Optional[str] = None


class ExtendDebateRequest(BaseModel):
    """Request to extend debate rounds or time"""
    extend_rounds: Optional[int] = Field(default=None, description="Additional rounds to add", ge=1, le=10)
    extend_minutes: Optional[int] = Field(default=None, description="Additional minutes to add", ge=5, le=120)
