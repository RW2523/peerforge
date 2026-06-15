"""Pydantic models for persona-related endpoints"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List


class GeneratePersonaDraftRequest(BaseModel):
    """Request to generate persona draft"""
    role_title: str = Field(..., min_length=1, max_length=100)
    style_brief: str = Field(..., min_length=1, max_length=500)
    tone: str = Field(..., min_length=1, max_length=100)
    risk_appetite: str = Field(..., min_length=1, max_length=100)
    model_id: str = Field(default="anthropic/claude-sonnet-4-5")


class PersonaTraits(BaseModel):
    """Persona trait scores"""
    assertiveness: float = Field(..., ge=1, le=10)
    analytical_depth: float = Field(..., ge=1, le=10)
    creativity: float = Field(..., ge=1, le=10)
    risk_tolerance: float = Field(..., ge=1, le=10)


class PersonaData(BaseModel):
    """Persona structure"""
    name: str = ""
    role_title: str
    description: str
    traits: PersonaTraits
    behavior_policy: str
    knowledge_policy: str


class GeneratePersonaDraftResponse(BaseModel):
    """Response from persona draft generation"""
    persona: PersonaData
    compiled_prompt: str


class ValidatePersonaRequest(BaseModel):
    """Request to validate persona"""
    persona: Dict[str, Any]
    compiled_prompt: str


class ValidatePersonaResponse(BaseModel):
    """Response from persona validation"""
    valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
