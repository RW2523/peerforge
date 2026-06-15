"""Pydantic models for meeting setup endpoints"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Literal, Optional
from .agents import SetupParticipant


class SetupMaterial(BaseModel):
    """Material metadata for setup"""
    kind: str = Field(..., pattern="^(text|link|file_placeholder)$")
    title: Optional[str] = None
    body_text: Optional[str] = None
    url: Optional[str] = None


class DebateSetupRequest(BaseModel):
    """Request to create debate with full setup"""
    model_config = ConfigDict(protected_namespaces=())

    workspace_id: str
    title: str
    problem_statement: str
    agenda: Optional[List[str]] = Field(default=None, description="Meeting agenda items")
    desired_outcomes: Optional[List[str]] = Field(default=None, description="Desired meeting outcomes")
    timebox_minutes: Optional[int] = None
    max_rounds: Optional[int] = Field(default=None, description="Number of rounds (each participant speaks once per round)")
    enable_host: Optional[bool] = Field(default=False, description="Enable Ultimate Host for final conclusion")
    host_model_id: Optional[str] = Field(default=None, description="AI model for host (only if enable_host=true)")
    # Deferred staffing: the setup wizard creates the session with an empty
    # panel right after Step 1 so materials can be uploaded before panel
    # selection. The "at least one participant" rule is enforced when the
    # session is STARTED, not when it is created.
    participants: List[SetupParticipant] = Field(default_factory=list)
    materials: Optional[List[SetupMaterial]] = Field(default_factory=list)
    reasoning_mode: Optional[Literal["light", "medium", "heavy"]] = Field(
        default="medium",
        description="Reasoning mode controls model selection across all AI activities"
    )


class DebateSetupResponse(BaseModel):
    """Response from debate setup"""
    debate_id: str
    participant_ids: List[str]
    material_ids: List[str]
