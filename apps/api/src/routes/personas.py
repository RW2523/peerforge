"""Persona generation and validation endpoints"""
from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional
import httpx
from ..persona_service import generate_persona_draft, validate_persona
from ..schemas.personas import (
    GeneratePersonaDraftRequest,
    GeneratePersonaDraftResponse,
    PersonaData,
    PersonaTraits,
    ValidatePersonaRequest,
    ValidatePersonaResponse,
)

router = APIRouter()


@router.post("/personas/generate-draft", response_model=GeneratePersonaDraftResponse)
async def generate_draft(
    request: GeneratePersonaDraftRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Generate persona draft using AI (OpenRouter BYOK).
    
    Requires OpenRouter API key in X-OpenRouter-Key header.
    Key is never stored.
    
    Headers:
        X-OpenRouter-Key: <openrouter-api-key>
    
    Returns:
        Persona structure + compiled system prompt
    
    Raises:
        400: Missing API key
        401: Invalid API key
        500: Generation failed
    """
    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key required in X-OpenRouter-Key header"
        )
    
    api_key = x_openrouter_key.strip()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key is empty"
        )
    
    try:
        persona_data = await generate_persona_draft(
            role_title=request.role_title,
            style_brief=request.style_brief,
            tone=request.tone,
            risk_appetite=request.risk_appetite,
            openrouter_api_key=api_key,
            model_id=request.model_id
        )
        
        # Extract compiled_prompt
        compiled_prompt = persona_data.pop("compiled_prompt", "")
        
        # Parse traits if dict
        if "traits" in persona_data and isinstance(persona_data["traits"], dict):
            persona_data["traits"] = PersonaTraits(**persona_data["traits"])
        
        return GeneratePersonaDraftResponse(
            persona=PersonaData(**persona_data),
            compiled_prompt=compiled_prompt
        )
    
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid OpenRouter API key"
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenRouter API error: {e.response.status_code}"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate persona: {str(e)}"
        )


@router.post("/personas/validate", response_model=ValidatePersonaResponse)
async def validate(request: ValidatePersonaRequest):
    """
    Validate persona structure and compiled prompt.
    
    No LLM call - pure validation logic.
    
    Returns:
        Validation result with errors/warnings
    """
    try:
        valid, errors, warnings = validate_persona(
            request.persona,
            request.compiled_prompt
        )
        
        return ValidatePersonaResponse(
            valid=valid,
            errors=errors,
            warnings=warnings
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Validation failed: {str(e)}"
        )
