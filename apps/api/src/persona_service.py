"""
Persona service - draft generation and validation.
"""
import httpx
import re
from typing import Dict, Any, List, Tuple


async def generate_persona_draft(
    role_title: str,
    style_brief: str,
    tone: str,
    risk_appetite: str,
    openrouter_api_key: str,
    model_id: str = "anthropic/claude-sonnet-4-5"
) -> Dict[str, Any]:
    """
    Generate persona draft using OpenRouter LLM.
    
    Args:
        role_title: Role/position title
        style_brief: Style description
        tone: Communication tone
        risk_appetite: Risk approach
        openrouter_api_key: User's OpenRouter key (BYOK)
        model_id: OpenRouter model to use
    
    Returns:
        Dict with persona fields and compiled_prompt
    """
    prompt = f"""Generate a participant persona for an AI-moderated decision meeting.

Role: {role_title}
Style: {style_brief}
Tone: {tone}
Risk Appetite: {risk_appetite}

Output JSON with these exact fields:
{{
  "name": "Optional display name or leave empty",
  "role_title": "{role_title}",
  "description": "1-sentence role description",
  "traits": {{
    "assertiveness": <1-10>,
    "analytical_depth": <1-10>,
    "creativity": <1-10>,
    "risk_tolerance": <1-10>
  }},
  "behavior_policy": "How this persona engages in discussions (2-3 sentences)",
  "knowledge_policy": "What domains/expertise this persona brings (2-3 sentences)",
  "compiled_prompt": "Full system prompt combining all above (150-300 words)"
}}

Ensure compiled_prompt is a complete system prompt ready for runtime use."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "HTTP-Referer": "https://arinar.ai",
                "X-Title": "Arinar Persona Generator",
                "Content-Type": "application/json"
            },
            json={
                "model": model_id,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 2000
            }
        )
        response.raise_for_status()
        data = response.json()
    
    # Extract JSON from response
    content = data["choices"][0]["message"]["content"]
    
    # Parse JSON (may be wrapped in markdown)
    import json
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        persona_data = json.loads(json_match.group(0))
    else:
        # Fallback: use raw content as compiled_prompt
        persona_data = {
            "name": "",
            "role_title": role_title,
            "description": f"{role_title} with {style_brief} style",
            "traits": {
                "assertiveness": 5,
                "analytical_depth": 5,
                "creativity": 5,
                "risk_tolerance": 5
            },
            "behavior_policy": f"{tone} communication style with {risk_appetite} risk approach",
            "knowledge_policy": f"Expertise in {role_title} domain",
            "compiled_prompt": content
        }
    
    return persona_data


def validate_persona(persona: Dict[str, Any], compiled_prompt: str) -> Tuple[bool, List[str], List[str]]:
    """
    Validate persona structure and compiled prompt.
    
    Returns:
        (valid, errors, warnings)
    """
    errors = []
    warnings = []
    
    # Required fields
    required = ["role_title", "description", "traits", "behavior_policy", "knowledge_policy"]
    for field in required:
        if field not in persona or not persona[field]:
            errors.append(f"Missing required field: {field}")
    
    # Traits validation
    if "traits" in persona:
        traits = persona["traits"]
        if not isinstance(traits, dict):
            errors.append("traits must be an object")
        else:
            for trait_name, value in traits.items():
                if not isinstance(value, (int, float)):
                    errors.append(f"Trait {trait_name} must be numeric")
                elif not (1 <= value <= 10):
                    errors.append(f"Trait {trait_name} must be between 1 and 10")
    
    # Compiled prompt validation
    if not compiled_prompt or len(compiled_prompt.strip()) == 0:
        errors.append("compiled_prompt cannot be empty")
    elif len(compiled_prompt) > 8000:
        errors.append("compiled_prompt exceeds 8000 characters")
    
    # Check for placeholder tokens
    if re.search(r'\{\{[^}]+\}\}', compiled_prompt):
        errors.append("compiled_prompt contains unresolved placeholder tokens like {{...}}")
    
    # Warnings
    if len(compiled_prompt) < 50:
        warnings.append("compiled_prompt is very short (<50 chars)")
    
    if "name" in persona and persona["name"]:
        if len(persona["name"]) > 50:
            warnings.append("name is unusually long (>50 chars)")
    
    valid = len(errors) == 0
    return valid, errors, warnings
