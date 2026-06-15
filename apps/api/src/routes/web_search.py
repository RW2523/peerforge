"""
PeerForge — Web Search Routes (Tavily)

POST /debates/{id}/web/search  — search the web via Tavily
POST /debates/{id}/web/save    — persist selected results as RAG context
GET  /debates/{id}/web         — list saved web results for this session
"""

import uuid
import logging
from typing import Any, Dict, List, Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import Json
from pydantic import BaseModel, Field

from src.auth import get_current_user
from src.config import settings
from src.database import get_db_connection, get_cursor
from src.debate_service import DebateService
from src.services.web_search import search_web, WebResult

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class WebSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000, description="Web search query")
    max_results: int = Field(default=10, ge=1, le=20, description="Number of results (max 20)")
    search_depth: str = Field(
        default="advanced",
        description="'basic' (fast) or 'advanced' (deeper, better quality)",
    )
    include_domains: Optional[List[str]] = Field(
        default=None,
        description="Restrict results to these domains, e.g. ['arxiv.org', 'nature.com']",
    )
    exclude_domains: Optional[List[str]] = Field(
        default=None,
        description="Exclude results from these domains",
    )


class WebResultOut(BaseModel):
    title: str
    url: str
    content: str
    score: float
    published_date: Optional[str]
    source_domain: str


class WebSearchResponse(BaseModel):
    query: str
    results: List[WebResultOut]
    total: int
    search_depth: str


class SaveWebResultsRequest(BaseModel):
    results: List[WebResultOut]
    label: Optional[str] = Field(default=None, description="Optional label for this batch")


class SaveWebResultsResponse(BaseModel):
    saved: int
    material_ids: List[str]


class SavedWebResult(BaseModel):
    material_id: str
    title: str
    url: str
    source_domain: str
    saved_at: str


class ListWebResultsResponse(BaseModel):
    results: List[SavedWebResult]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/debates/{debate_id}/web/search",
    response_model=WebSearchResponse,
)
async def web_search(
    debate_id: str,
    body: WebSearchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Search the web via Tavily and return ranked results.

    Returns up to max_results curated web pages. Does NOT persist anything —
    call /web/save to add selected results to the review context.

    Requires TAVILY_API_KEY to be set in the API environment.
    """
    if not settings.tavily_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Web search is not configured. "
                "Set TAVILY_API_KEY in apps/api/.env — get a free key at https://tavily.com"
            ),
        )

    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        results = await search_web(
            query=body.query,
            max_results=body.max_results,
            search_depth=body.search_depth,
            include_domains=body.include_domains,
            exclude_domains=body.exclude_domains,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except Exception as exc:
        logger.error("Web search failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Tavily search failed: {exc}",
        )

    return WebSearchResponse(
        query=body.query,
        results=[WebResultOut(**r.to_dict()) for r in results],
        total=len(results),
        search_depth=body.search_depth,
    )


@router.post(
    "/debates/{debate_id}/web/save",
    response_model=SaveWebResultsResponse,
)
async def save_web_results(
    debate_id: str,
    body: SaveWebResultsRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Persist selected web results into the review session's RAG context.

    Each result is stored as a meeting_material (kind='web') and its content
    is also saved to memory_chunks for semantic retrieval during AI reviews.
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    material_ids: List[str] = []

    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)

            for result in body.results:
                wr = WebResult(
                    title=result.title,
                    url=result.url,
                    content=result.content,
                    score=result.score,
                    published_date=result.published_date,
                    source_domain=result.source_domain,
                )
                chunk_text = wr.to_chunk_text()
                material_id = str(uuid.uuid4())

                cursor.execute(
                    """
                    INSERT INTO meeting_materials (
                        material_id, debate_id, kind, title,
                        body_text, url, processed_status, processing_metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, 'web', %s,
                        %s, %s, 'complete', %s, NOW(), NOW()
                    )
                    ON CONFLICT (material_id) DO NOTHING
                    """,
                    (
                        material_id,
                        debate_id,
                        result.title[:255],
                        chunk_text,
                        result.url or None,
                        Json({
                            "source": "tavily",
                            "source_domain": result.source_domain,
                            "score": result.score,
                            "published_date": result.published_date,
                            "label": body.label,
                            "saved_by": "web_search",
                        }),
                    ),
                )

                # Insert content as a memory chunk for semantic retrieval.
                # Literature-style ownership: source_debate_id, no agent_id.
                chunk_id = str(uuid.uuid4())
                cursor.execute(
                    """
                    INSERT INTO memory_chunks (
                        chunk_id, agent_id, source_debate_id,
                        chunk_text, chunk_metadata, created_at
                    ) VALUES (
                        %s, NULL, %s,
                        %s, %s, NOW()
                    )
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    (
                        chunk_id,
                        debate_id,
                        chunk_text[:4000],
                        Json({
                            "material_id": material_id,
                            "source": "tavily",
                            "source_domain": result.source_domain,
                            "web_title": result.title,
                            "url": result.url,
                            "saved_by": "web_search",
                        }),
                    ),
                )

                material_ids.append(material_id)

            conn.commit()
    except psycopg2.Error as exc:
        logger.error("Failed to save web results: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist web results to review context",
        )

    return SaveWebResultsResponse(saved=len(material_ids), material_ids=material_ids)


@router.get(
    "/debates/{debate_id}/web",
    response_model=ListWebResultsResponse,
)
async def list_web_results(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all web search results saved to a review session's context."""
    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    with get_db_connection() as conn:
        cursor = get_cursor(conn)
        cursor.execute(
            """
            SELECT material_id, title, url, processing_metadata, created_at
            FROM meeting_materials
            WHERE debate_id = %s AND kind = 'web'
            ORDER BY created_at DESC
            """,
            (debate_id,),
        )
        rows = cursor.fetchall()

    results = []
    for row in rows:
        meta = row.get("processing_metadata") or {}
        results.append(
            SavedWebResult(
                material_id=str(row["material_id"]),
                title=row["title"] or "",
                url=row["url"] or "",
                source_domain=meta.get("source_domain", ""),
                saved_at=row["created_at"].isoformat() if row["created_at"] else "",
            )
        )

    return ListWebResultsResponse(results=results, total=len(results))
