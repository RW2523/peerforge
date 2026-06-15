"""AI assistance endpoints for improving user input"""
from fastapi import APIRouter, HTTPException, status, Header
from pydantic import BaseModel
from typing import Optional
import httpx
import asyncio
import json
import re
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ProblemStatementRequest(BaseModel):
    input_text: str


class ProblemStatementResponse(BaseModel):
    improved_text: str
    key_points: list[str]
    agenda_items: list[str]
    desired_outcomes: list[str]


class HealthCheckResponse(BaseModel):
    status: str
    model: str
    credits_available: bool


@router.get("/ai/health", response_model=HealthCheckResponse)
async def health_check(
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """Quick health check for OpenRouter API key"""
    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key required"
        )
    
    if not x_openrouter_key.startswith('sk-or-'):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format"
        )
    
    try:
        # Quick test with minimal tokens
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {x_openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                }
            )
            
            if response.status_code == 200:
                return HealthCheckResponse(
                    status="ok",
                    model="openai/gpt-4o-mini",
                    credits_available=True
                )
            elif response.status_code == 402:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Insufficient credits"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"OpenRouter error: {response.status_code}"
                )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="OpenRouter timeout"
        )
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )


@router.post("/ai/improve-problem-statement", response_model=ProblemStatementResponse)
async def improve_problem_statement(
    request: ProblemStatementRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Improve a problem statement for debate using AI.
    Uses cost-effective Claude Haiku model.
    """
    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key required (X-OpenRouter-Key header)"
        )
    
    # Quick validation - key should start with sk-or-
    if not x_openrouter_key.startswith('sk-or-'):
        logger.warning(f"Invalid API key format: {x_openrouter_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OpenRouter API key format. Keys should start with 'sk-or-'. Get a key at openrouter.ai"
        )
    
    if not request.input_text or len(request.input_text.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input text must be at least 10 characters"
        )
    
    # Use GPT-4o-mini - most cost effective for structured output ($0.15/$0.60)
    model = "openai/gpt-4o-mini"
    
    system_prompt = """You are an expert at structuring multi-agent debates and meetings.

Your task: Take the user's rough problem statement and create a complete debate structure including:
1. An improved, debate-worthy problem statement
2. Key discussion points
3. Meeting agenda items
4. Desired outcomes

Guidelines:
- Make the problem statement clear, concise, and specific (under 200 words)
- Frame it as a question or problem with multiple valid perspectives
- Create 3-5 key discussion points
- Suggest 3-4 agenda items for the meeting
- Define 2-3 desired outcomes

STRICT OUTPUT FORMAT (you MUST follow this exactly):
```
PROBLEM STATEMENT:
[Write the improved problem statement here]

KEY POINTS:
- [Point 1]
- [Point 2]
- [Point 3]

AGENDA:
- [Agenda item 1]
- [Agenda item 2]
- [Agenda item 3]

DESIRED OUTCOMES:
- [Outcome 1]
- [Outcome 2]
```

Example:
Input: "we need to figure out what to do about sales"
Output:
```
PROBLEM STATEMENT:
How should our organization restructure its sales strategy to achieve 30% growth in Q2 while maintaining customer satisfaction and team morale?

KEY POINTS:
- Revenue growth targets and timeline
- Customer experience and retention
- Sales team capacity and motivation
- Resource allocation and budgeting
- Market conditions and competition

AGENDA:
- Review current sales performance and identify gaps
- Discuss proposed strategies and resource requirements
- Evaluate impact on team and customers
- Create action plan with ownership and timelines

DESIRED OUTCOMES:
- Agreement on specific growth strategy with measurable targets
- Clear action plan with assigned responsibilities
- Commitment to maintaining customer satisfaction scores above 8.5/10
```"""
    
    user_prompt = f"""Create a complete debate structure for this topic:

"{request.input_text}"

Remember to follow the EXACT format with all four sections: PROBLEM STATEMENT, KEY POINTS, AGENDA, and DESIRED OUTCOMES."""
    
    try:
        # Retry logic for rate limits
        max_retries = 2
        retry_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                # Shorter timeout to fail fast - use httpx.Timeout for more control
                timeout_config = httpx.Timeout(
                    connect=5.0,  # 5 seconds to connect
                    read=15.0,    # 15 seconds to read response
                    write=5.0,    # 5 seconds to send request
                    pool=5.0      # 5 seconds to get connection from pool
                )
                
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    logger.info(f"Calling OpenRouter with {model} (attempt {attempt + 1}/{max_retries})")
                    
                    response = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {x_openrouter_key}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://github.com/yourusername/arinar",  # Optional
                            "X-Title": "Arinar Debate Platform",  # Optional
                        },
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            "max_tokens": 800,
                            "temperature": 0.7,
                        }
                    )
                    
                    logger.info(f"OpenRouter responded with status {response.status_code}")
                    
                    if response.status_code == 429:
                        if attempt < max_retries - 1:
                            logger.warning(f"Rate limited (429), retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                                detail="AI service rate limit exceeded. Please try again in a moment."
                            )
                    
                    if response.status_code != 200:
                        error_text = response.text[:200]  # Truncate for logging
                        logger.error(f"OpenRouter API error: {response.status_code} - {error_text}")
                        
                        # Better error messages
                        if response.status_code == 401:
                            raise HTTPException(
                                status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid API key. Please check your OpenRouter API key in Settings."
                            )
                        elif response.status_code == 402:
                            raise HTTPException(
                                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                                detail="OpenRouter account has insufficient credits. Please add credits at openrouter.ai"
                            )
                        else:
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"AI service error ({response.status_code}). Please try again."
                            )
                    
                    result = response.json()
                    ai_output = result["choices"][0]["message"]["content"]
                    break  # Success, exit retry loop
                    
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 and attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise
            
        # Parse the structured output
        improved_text = ""
        key_points = []
        agenda_items = []
        desired_outcomes = []
        
        # Extract sections
        sections = {
            "PROBLEM STATEMENT:": "improved_text",
            "KEY POINTS:": "key_points",
            "AGENDA:": "agenda_items",
            "DESIRED OUTCOMES:": "desired_outcomes"
        }
        
        current_section = None
        current_content = []
        
        for line in ai_output.split('\n'):
            line = line.strip()
            
            # Check if this is a section header
            section_found = False
            for header, var_name in sections.items():
                if header in line:
                    # Save previous section
                    if current_section:
                        if current_section == "improved_text":
                            improved_text = '\n'.join(current_content).strip()
                        else:
                            # Extract bullet points
                            items = [
                                l.lstrip('-').lstrip('•').lstrip('*').strip()
                                for l in current_content
                                if l and (l.startswith('-') or l.startswith('•') or l.startswith('*'))
                            ]
                            if current_section == "key_points":
                                key_points = items
                            elif current_section == "agenda_items":
                                agenda_items = items
                            elif current_section == "desired_outcomes":
                                desired_outcomes = items
                    
                    current_section = var_name
                    current_content = []
                    section_found = True
                    break
            
            if not section_found and current_section and line:
                current_content.append(line)
        
        # Save last section
        if current_section:
            if current_section == "improved_text":
                improved_text = '\n'.join(current_content).strip()
            else:
                items = [
                    l.lstrip('-').lstrip('•').lstrip('*').strip()
                    for l in current_content
                    if l and (l.startswith('-') or l.startswith('•') or l.startswith('*'))
                ]
                if current_section == "key_points":
                    key_points = items
                elif current_section == "agenda_items":
                    agenda_items = items
                elif current_section == "desired_outcomes":
                    desired_outcomes = items
        
        # Fallback if parsing failed
        if not improved_text:
            improved_text = ai_output.strip()
        
        return ProblemStatementResponse(
            improved_text=improved_text,
            key_points=key_points,
            agenda_items=agenda_items,
            desired_outcomes=desired_outcomes
        )
            
    except httpx.TimeoutException:
        logger.error("OpenRouter timeout after 20s")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service is slow to respond. Please try again or check openrouter.ai status."
        )
    except httpx.RequestError as e:
        logger.error(f"Request error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Network error connecting to AI service. Check your internet connection."
        )
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to improve problem statement: {str(e)}"
        )


# ── Panel suggestion ─────────────────────────────────────────────────────────

class PanelTemplateInfo(BaseModel):
    template_id: str
    label: str
    role_title: str = ""
    category: str = ""
    character: str = ""


class PanelSuggestRequest(BaseModel):
    title: str
    abstract: str = ""
    templates: list[PanelTemplateInfo]
    n: int = 5


class PanelSuggestion(BaseModel):
    template_id: str
    reason: str


class PanelSuggestResponse(BaseModel):
    suggestions: list[PanelSuggestion]
    model_used: str


@router.post("/ai/suggest-panel", response_model=PanelSuggestResponse)
async def suggest_panel(
    request: PanelSuggestRequest,
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
):
    """
    Read the session title + abstract and rank the most relevant agent
    templates for the review panel. Returns the top-N template ids with a
    one-sentence reason each, grounded in the research topic.
    """
    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key required (X-OpenRouter-Key header)",
        )
    if not request.title.strip() and not request.abstract.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a title or abstract first so the AI can match panel members.",
        )
    if not request.templates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No templates provided.",
        )

    n = max(1, min(request.n, len(request.templates), 8))
    catalog = "\n".join(
        f"- id: {t.template_id} | {t.label} | role: {t.role_title} | category: {t.category}"
        + (f" | character: {t.character}" if t.character else "")
        for t in request.templates
    )

    system_prompt = (
        "You are an academic review panel designer. Given a research title and "
        "abstract, select the most relevant reviewer templates from a catalog.\n"
        "Selection principles:\n"
        "- Cover complementary review lanes: methodology, domain expertise, "
        "skeptical claim-checking, clarity/communication, and independent scrutiny.\n"
        "- Match the research domain: prefer reviewers whose expertise fits the topic.\n"
        "- Never pick two templates that duplicate the same lane.\n"
        "- Each reason must reference the specific research topic, not generic praise.\n"
        f"Return ONLY a JSON array of exactly {n} objects, ordered most relevant first:\n"
        '[{"template_id": "<id from catalog>", "reason": "<one sentence tied to this research>"}]'
    )
    user_prompt = (
        f"## Research Title\n{request.title.strip() or '(not provided)'}\n\n"
        f"## Abstract / Research Question\n{request.abstract.strip() or '(not provided)'}\n\n"
        f"## Template Catalog\n{catalog}\n\n"
        f"Pick the top {n} templates for this research and return the JSON array."
    )

    model = "openai/gpt-4o-mini"
    try:
        timeout_config = httpx.Timeout(connect=5.0, read=25.0, write=5.0, pool=5.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {x_openrouter_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "max_tokens": 900,
                    "temperature": 0.3,
                },
            )
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Invalid API key. Check your OpenRouter key in Settings.")
        if response.status_code == 402:
            raise HTTPException(status_code=402, detail="OpenRouter account has insufficient credits.")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"AI service error ({response.status_code}). Please try again.")

        raw = response.json()["choices"][0]["message"]["content"].strip()
        raw = re.sub(r"^```(?:json)?\s*\n?", "", raw)
        raw = re.sub(r"\n?```\s*$", "", raw)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\[[\s\S]+\]", raw)
            if not match:
                raise HTTPException(status_code=502, detail="AI returned an unreadable suggestion. Please try again.")
            parsed = json.loads(match.group(0))

        valid_ids = {t.template_id for t in request.templates}
        suggestions: list[PanelSuggestion] = []
        seen: set = set()
        for item in parsed:
            tid = str(item.get("template_id", "")).strip()
            if tid in valid_ids and tid not in seen:
                seen.add(tid)
                suggestions.append(PanelSuggestion(
                    template_id=tid,
                    reason=str(item.get("reason", "")).strip() or "Relevant to this research.",
                ))
            if len(suggestions) >= n:
                break

        if not suggestions:
            raise HTTPException(status_code=502, detail="AI did not match any catalog templates. Please try again.")

        return PanelSuggestResponse(suggestions=suggestions, model_used=model)

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI service is slow to respond. Please try again.")
    except Exception as exc:
        logger.error(f"suggest_panel failed: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to suggest panel: {exc}")
