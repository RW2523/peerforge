"""OpenRouter integration endpoints"""
from fastapi import APIRouter, HTTPException, status, Header
from typing import Optional, Dict, Any
import httpx
from ..openrouter_models_service import fetch_openrouter_models
from ..schemas.openrouter import ModelListResponse, OpenRouterModel

router = APIRouter()


@router.get("/openrouter/models", response_model=ModelListResponse)
async def list_openrouter_models(
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key")
):
    """
    Fetch OpenRouter model catalog using user's BYOK key.
    
    Key is never stored - only used for this request.
    Results are cached in-memory for 60s per key hash.
    
    Headers:
        X-OpenRouter-Key: <openrouter-api-key>
    
    Returns:
        List of available models
    
    Raises:
        400: Missing or invalid API key
        401: OpenRouter authentication failed
        500: OpenRouter API error
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
        models = await fetch_openrouter_models(api_key)
        return ModelListResponse(
            models=[OpenRouterModel(**m) for m in models],
            cached=False  # TODO(TICKET-08C.2B): track cache status from service layer
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
            detail=f"Failed to fetch models: {str(e)}"
        )


@router.get("/openrouter/account")
async def get_openrouter_account(
    x_openrouter_key: Optional[str] = Header(None, alias="X-OpenRouter-Key"),
    x_openrouter_management_key: Optional[str] = Header(None, alias="X-OpenRouter-Management-Key")
) -> Dict[str, Any]:
    """
    Get OpenRouter account info: usage, limits, credits.
    
    Uses user's BYOK key to fetch account details from OpenRouter.
    Keys are never stored.
    
    Headers:
        X-OpenRouter-Key: <openrouter-api-key> (required - for validation)
        X-OpenRouter-Management-Key: <management-key> (optional - for credits)
    
    Returns:
        Account info including key validation, models available, and credits (if management key provided)
    
    Raises:
        400: Missing API key
        401: Invalid API key
        500: OpenRouter API error
    """
    if not x_openrouter_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key required in X-OpenRouter-Key header"
        )
    
    api_key = x_openrouter_key.strip()
    management_key = x_openrouter_management_key.strip() if x_openrouter_management_key else None
    
    # Debug logging
    print(f"🔑 Account request received:")
    print(f"  API Key: {api_key[:20]}... (len={len(api_key)})")
    print(f"  Management Key: {management_key[:20] if management_key else 'None'}... (len={len(management_key) if management_key else 0})")
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OpenRouter API key is empty"
        )
    
    async with httpx.AsyncClient() as client:
        try:
            # Validate key by making a minimal chat completion request
            # This actually requires authentication unlike the models endpoint
            validation_response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://arinar.ai",
                    "X-Title": "Arinar"
                },
                json={
                    "model": "openai/gpt-4o-mini",
                    "messages": [{"role": "user", "content": "test"}],
                    "max_tokens": 1
                },
                timeout=15.0
            )
            validation_response.raise_for_status()
            
            # Key is valid, now fetch models list for UI
            models_response = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            )
            models_response.raise_for_status()
            models_data = models_response.json()
            model_count = len(models_data.get("data", []))
            
            # Try to fetch key info (requires management/dashboard key)
            key_data = None
            key_to_check = management_key if management_key else api_key
            
            try:
                key_response = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {key_to_check}"},
                    timeout=10.0
                )
                if key_response.status_code == 200:
                    key_data = key_response.json().get("data", {})
            except Exception as e:
                # Management endpoints not available for regular keys (expected)
                print(f"Key info endpoint unavailable: {e}")
            
            # Try to fetch credits (use management key if provided, otherwise try regular key)
            credits_data = None
            credits_balance = None
            
            if management_key:
                try:
                    print(f"💰 Fetching credits with management key...")
                    credits_response = await client.get(
                        "https://openrouter.ai/api/v1/credits",
                        headers={"Authorization": f"Bearer {management_key}"},
                        timeout=10.0
                    )
                    print(f"  Credits API status: {credits_response.status_code}")
                    if credits_response.status_code == 200:
                        credits_data = credits_response.json().get("data")
                        if credits_data:
                            # Calculate balance
                            total_credits = credits_data.get("total_credits", 0)
                            total_usage = credits_data.get("total_usage", 0)
                            credits_balance = total_credits - total_usage
                            print(f"  ✅ Credits fetched: balance=${credits_balance}")
                        else:
                            print(f"  ⚠️  Credits response has no 'data' field")
                    else:
                        print(f"  ⚠️  Credits API returned non-200: {credits_response.status_code}")
                        print(f"  Response: {credits_response.text[:200]}")
                except Exception as e:
                    print(f"❌ Credits endpoint error with management key: {e}")
            
            # Build response
            note = None
            if not management_key:
                note = "Add management API key to view credits balance."
            elif not credits_data:
                note = "Could not fetch credits. Check management key permissions."
            
            response_data = {
                "key": key_data or {
                    "label": "API Key",
                    "is_valid": True,
                    "validated_via": "models_endpoint"
                },
                "credits": {
                    "total_credits": credits_data.get("total_credits") if credits_data else None,
                    "total_usage": credits_data.get("total_usage") if credits_data else None,
                    "balance": credits_balance
                } if credits_data else None,
                "models_available": model_count,
                "has_management_key": management_key is not None,
                "note": note
            }
            
            print(f"📤 Returning response:")
            print(f"  has_management_key: {response_data['has_management_key']}")
            print(f"  credits: {response_data['credits']}")
            print(f"  note: {response_data['note']}")
            
            return response_data
        
        except httpx.HTTPStatusError as e:
            error_text = e.response.text
            status_code = e.response.status_code
            
            # Parse error message for better user feedback
            if status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid OpenRouter API key - please check your key and try again"
                )
            elif status_code == 502:
                # Check if it's the Clerk authentication issue
                if "Clerk" in error_text or "authentication" in error_text.lower():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="OpenRouter authentication service (Clerk) is temporarily unavailable. Please try again in a few minutes, or get a fresh API key from openrouter.ai/keys"
                    )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="OpenRouter service error - please try again later"
                )
            elif status_code == 429:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="OpenRouter rate limit exceeded - please wait a moment and try again"
                )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"OpenRouter API error ({status_code}): {error_text[:200]}"
            )
        
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="OpenRouter request timed out - please check your connection and try again"
            )
        
        except Exception as e:
            error_message = str(e)
            # Check for common network errors
            if "connection" in error_message.lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Cannot connect to OpenRouter - please check your internet connection"
                )
            
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to validate OpenRouter key: {error_message[:200]}"
            )
