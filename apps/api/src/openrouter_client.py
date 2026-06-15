"""OpenRouter client abstraction (OpenRouter-only policy)"""
import httpx
import time
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from .config import settings


class OpenRouterError(Exception):
    """Base exception for OpenRouter errors"""
    pass


class OpenRouterAuthError(OpenRouterError):
    """Authentication/authorization error"""
    pass


class OpenRouterClient:
    """
    OpenRouter API client
    
    Enforces OpenRouter-only model provider policy.
    BYOK (Bring Your Own Key) - key provided per request.
    """
    
    def __init__(self, api_key: str):
        """
        Initialize OpenRouter client
        
        Args:
            api_key: OpenRouter API key (user-provided per request)
        """
        if not api_key or not api_key.strip():
            raise OpenRouterAuthError("OpenRouter API key is required")
        
        self.api_key = api_key.strip()
        self.base_url = settings.openrouter_base_url
        self.timeout = settings.openrouter_timeout
        self.max_retries = settings.openrouter_max_retries
    
    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def chat_completion(
        self,
        model: str,
        messages: list[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        # Eval-logger context (never forwarded to OpenRouter)
        _debate_id: Optional[str] = None,
        _stage: str = "unknown",
        _participant: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request chat completion from OpenRouter
        
        Args:
            model: Model identifier (e.g. "anthropic/claude-sonnet-4-5")
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature
            max_tokens: Optional max tokens limit
        
        Returns:
            Response dict with "content" and "usage" fields
        
        Raises:
            OpenRouterAuthError: Invalid/missing API key
            OpenRouterError: Other API errors
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://arinar.ai",
            "X-Title": "Arinar Debate Platform"
        }
        
        # Validate model parameter
        if not model or (isinstance(model, str) and model.strip() == ''):
            raise ValueError(f"Invalid model parameter: {repr(model)}. Model cannot be empty.")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        t_start = time.monotonic()
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )

                if response.status_code == 401:
                    raise OpenRouterAuthError("Invalid OpenRouter API key")
                elif response.status_code == 403:
                    raise OpenRouterAuthError("OpenRouter API key lacks required permissions")
                elif response.status_code != 200:
                    error_detail = response.text
                    raise OpenRouterError(f"OpenRouter API error (status {response.status_code}): {error_detail}")

                data = response.json()

                if "choices" not in data or len(data["choices"]) == 0:
                    raise OpenRouterError("No choices in OpenRouter response")

                choice = data["choices"][0]
                content = choice.get("message", {}).get("content", "")
                result = {
                    "content": content,
                    "usage": data.get("usage", {}),
                    "model": data.get("model", model),
                }

                # ── Eval log ──────────────────────────────────────────────
                if _debate_id:
                    try:
                        from .services.eval_logger import get_logger
                        get_logger(_debate_id).log_llm_call(
                            stage=_stage,
                            model=result["model"],
                            messages=messages,
                            response_content=content,
                            usage=result["usage"],
                            latency_ms=int((time.monotonic() - t_start) * 1000),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            participant=_participant,
                        )
                    except Exception as _log_exc:
                        print(f"[eval_logger] log_llm_call failed: {_log_exc}")
                # ─────────────────────────────────────────────────────────

                return result

        except (OpenRouterAuthError, OpenRouterError):
            if _debate_id:
                try:
                    from .services.eval_logger import get_logger
                    get_logger(_debate_id).log_llm_call(
                        stage=_stage,
                        model=model,
                        messages=messages,
                        response_content=None,
                        usage=None,
                        latency_ms=int((time.monotonic() - t_start) * 1000),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        participant=_participant,
                        error="OpenRouter error — see API logs",
                    )
                except Exception:
                    pass
            raise
        except httpx.TimeoutException:
            raise OpenRouterError(f"OpenRouter request timed out after {self.timeout}s")
        except httpx.RequestError as e:
            raise OpenRouterError(f"OpenRouter request failed: {str(e)}")
