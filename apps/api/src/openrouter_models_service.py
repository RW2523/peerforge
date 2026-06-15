"""
OpenRouter Models Service - fetches model catalog from OpenRouter API.
Never stores raw API keys.
"""
import httpx
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class OpenRouterModelsCache:
    """In-memory cache for model listings (60s TTL per key hash)"""
    
    def __init__(self):
        self._cache: Dict[str, tuple[List[Dict[str, Any]], datetime]] = {}
    
    def get(self, key_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached models if not expired"""
        if key_hash in self._cache:
            models, timestamp = self._cache[key_hash]
            if datetime.utcnow() - timestamp < timedelta(seconds=60):
                return models
            else:
                del self._cache[key_hash]
        return None
    
    def set(self, key_hash: str, models: List[Dict[str, Any]]):
        """Cache models list"""
        self._cache[key_hash] = (models, datetime.utcnow())


# Global cache instance
_models_cache = OpenRouterModelsCache()


def _hash_key(api_key: str) -> str:
    """Hash API key for cache lookup (never store raw key)"""
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


async def fetch_openrouter_models(api_key: str) -> List[Dict[str, Any]]:
    """
    Fetch model catalog from OpenRouter API.
    
    Args:
        api_key: User's OpenRouter API key (BYOK, never stored)
    
    Returns:
        List of models with normalized fields: id, name, context_length, pricing
    
    Raises:
        httpx.HTTPStatusError: If API request fails
    """
    key_hash = _hash_key(api_key)
    
    # Check cache
    cached = _models_cache.get(key_hash)
    if cached:
        return cached
    
    # Fetch from OpenRouter
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://arinar.ai",
                "X-Title": "Arinar Decision Room"
            }
        )
        response.raise_for_status()
        data = response.json()
    
    # Normalize response
    models = []
    for model in data.get("data", []):
        models.append({
            "id": model.get("id"),
            "name": model.get("name") or model.get("id"),
            "context_length": model.get("context_length"),
            "pricing": model.get("pricing"),
            "description": model.get("description"),
        })
    
    # Cache
    _models_cache.set(key_hash, models)
    
    return models
