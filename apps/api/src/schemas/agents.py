"""Pydantic models for agent-related endpoints"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List


class AgentInput(BaseModel):
    """Agent configuration for debate"""
    model_config = ConfigDict(protected_namespaces=())
    
    name: str = Field(..., description="Agent display name")
    role: str = Field(..., description="Agent role description")
    model_id: str = Field(..., description="OpenRouter model ID (e.g. anthropic/claude-3.5-sonnet)")


class AgentTemplateResponse(BaseModel):
    """Agent template with category and character"""
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    
    template_id: str
    label: str
    role_title: str
    category: str
    character: Optional[str] = None
    system_prompt: str
    model_id: str
    llm_config: Dict[str, Any] = Field(..., alias="model_config")


class CreateAgentRequest(BaseModel):
    """Request to create persistent agent"""
    model_config = ConfigDict(protected_namespaces=())
    
    workspace_id: str
    name: str
    role_description: Optional[str] = None
    system_prompt: str
    model_id: str
    agent_model_config: Optional[Dict[str, Any]] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Agent response"""
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    
    agent_id: str
    workspace_id: str
    name: str
    role_description: Optional[str]
    system_prompt: str
    model_id: str
    llm_config: Dict[str, Any] = Field(..., alias="model_config")
    created_at: str


class SetupParticipant(BaseModel):
    """Participant for setup flow"""
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    
    agent_id: Optional[str] = None  # Use existing agent
    name: Optional[str] = None  # For inline config
    role_description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_id: Optional[str] = None
    llm_config: Optional[Dict[str, Any]] = Field(default=None, alias="model_config")
