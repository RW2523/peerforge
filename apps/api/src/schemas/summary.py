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
    
    openrouter_api_key: str = Field(..., description="OpenRouter BYOK key (never stored)", min_length=10)
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
