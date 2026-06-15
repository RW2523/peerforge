"""
PeerForge — Tavily Web Search Service

Wraps the Tavily Search API to retrieve high-quality, AI-curated web results
relevant to a research topic.  Returns a list of WebResult objects that can be
saved into the review session's RAG context (meeting_materials / memory_chunks).

Tavily is preferred over raw web search because it:
  - Filters junk / paywalled pages automatically
  - Returns clean extracted content (no HTML parsing needed)
  - Has a dedicated "research" search depth option
  - Optionally includes image links and raw content
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class WebResult:
    title: str
    url: str
    content: str          # Tavily-extracted page snippet / summary
    raw_content: str = "" # Full page text (only when include_raw_content=True)
    score: float = 0.0    # Relevance score from Tavily (0-1)
    published_date: Optional[str] = None
    source_domain: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "score": round(self.score, 4),
            "published_date": self.published_date,
            "source_domain": self.source_domain,
        }

    def to_chunk_text(self) -> str:
        """Format for storage in memory_chunks / RAG retrieval."""
        lines = [f"[WEB] {self.title}", f"URL: {self.url}"]
        if self.published_date:
            lines.append(f"Published: {self.published_date}")
        if self.source_domain:
            lines.append(f"Source: {self.source_domain}")
        lines.append("")
        lines.append(self.content)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Search function
# ---------------------------------------------------------------------------

async def search_web(
    query: str,
    max_results: int = 10,
    search_depth: str = "advanced",
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    topic: str = "general",
) -> List[WebResult]:
    """
    Run a Tavily web search and return structured WebResult objects.

    Args:
        query:            Search query string (≤400 chars recommended for best results).
        max_results:      Number of results to return (1-20, Tavily limit).
        search_depth:     "basic" (faster, lower cost) or "advanced" (deeper, better quality).
        include_domains:  Whitelist specific domains (e.g. ["scholar.google.com"]).
        exclude_domains:  Blacklist domains to skip.
        topic:            "general" | "news" | "research" — hints the Tavily ranker.

    Returns:
        List of WebResult objects sorted by relevance score descending.

    Raises:
        RuntimeError if TAVILY_API_KEY is not configured.
        Exception for network / API errors (caller should handle gracefully).
    """
    api_key = settings.tavily_api_key
    if not api_key:
        raise RuntimeError(
            "TAVILY_API_KEY is not configured. "
            "Get a free key at https://tavily.com and set it in apps/api/.env"
        )

    try:
        from tavily import TavilyClient  # type: ignore
    except ImportError:
        raise RuntimeError(
            "tavily-python is not installed. Run: pip install tavily-python"
        )

    client = TavilyClient(api_key=api_key)

    kwargs: dict = {
        "query": query[:400],
        "search_depth": search_depth,
        "max_results": min(max_results, 20),
        "include_answer": False,
        "include_raw_content": False,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    if exclude_domains:
        kwargs["exclude_domains"] = exclude_domains

    try:
        response = client.search(**kwargs)
    except Exception as exc:
        logger.error("Tavily search failed for query %r: %s", query[:80], exc)
        raise

    results: List[WebResult] = []
    for item in response.get("results", []):
        url = item.get("url", "")
        domain = _extract_domain(url)
        results.append(
            WebResult(
                title=item.get("title", url),
                url=url,
                content=item.get("content", ""),
                score=float(item.get("score", 0)),
                published_date=item.get("published_date"),
                source_domain=domain,
            )
        )

    results.sort(key=lambda r: r.score, reverse=True)
    logger.info(
        "Tavily search returned %d results for query %r",
        len(results), query[:60],
    )
    return results


def _extract_domain(url: str) -> str:
    """Extract base domain from a URL for display."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.removeprefix("www.")
    except Exception:
        return ""
