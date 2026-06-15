"""Pydantic models for OpenRouter-related endpoints"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class OpenRouterModel(BaseModel):
    """OpenRouter model info"""
    id: str
    name: str
    context_length: Optional[int] = None
    pricing: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class ModelListResponse(BaseModel):
    """Response from /openrouter/models"""
    models: List[OpenRouterModel]
    cached: bool = False
