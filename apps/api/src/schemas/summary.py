"""Pydantic models for summary-related endpoints"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional


class ActionItem(BaseModel):
    """Action item from debate summary"""
    description: str
    owner: str
    priority: str


class SummarizeRequest(BaseModel):
    """Request to generate debate summary (M3)"""
    model_config = ConfigDict(protected_namespaces=())
    
    # Optional: omitted when the caller relies on the key stored on their
    # account or configured on the server. Required-with-min_length made
    # the request 422 before the handler could resolve either.
    openrouter_api_key: Optional[str] = Field(
        default=None, description="OpenRouter BYOK key (never stored)"
    )
    model_id: str = Field(default="anthropic/claude-sonnet-4-5", description="Model for summary generation")


class SummaryResponse(BaseModel):
    """Debate summary outputs (M3)"""
    model_config = ConfigDict(protected_namespaces=())
    
    output_id: str
    debate_id: str
    summary: str
    minutes: str
    action_items: List[ActionItem]
    generated_at: str
    model_used: Optional[str] = None
