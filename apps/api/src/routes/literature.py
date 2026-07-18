"""
PeerForge — Literature Search Routes

POST /debates/{id}/literature/search  — search academic databases
POST /debates/{id}/literature/save    — persist selected papers as RAG chunks
GET  /debates/{id}/literature         — list saved papers for this session
"""

import uuid
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import psycopg2
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import Json
from pydantic import BaseModel, Field

from src.auth import get_current_user
from src.database import get_db_connection, get_cursor
from src.debate_service import DebateService
from src.services.literature_search import (
    ALL_SOURCES,
    search_literature,
    paper_to_chunk_text,
    Paper,
)
from src.services.committee_twin import build_committee_twins

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LiteratureSearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    sources: Optional[List[str]] = Field(default=None, description="Subset of: arxiv, semantic_scholar, pubmed, crossref, openalex")
    max_per_source: int = Field(default=8, ge=1, le=20)
    max_total: int = Field(default=25, ge=1, le=50)


class PaperResult(BaseModel):
    title: str
    authors: List[str]
    year: Optional[int]
    abstract: str
    url: str
    doi: Optional[str]
    venue: str
    citation_count: int
    source: str


class LiteratureSearchResponse(BaseModel):
    query: str
    papers: List[PaperResult]
    total: int
    sources_queried: List[str]


class SavePapersRequest(BaseModel):
    papers: List[PaperResult]
    label: Optional[str] = Field(default=None, description="Optional label for this batch of saved papers")


class ReviewerInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    affiliation: Optional[str] = Field(default="", max_length=200)
    role: Optional[str] = Field(default=None)


class CommitteeTwinRequest(BaseModel):
    reviewers: List[ReviewerInput] = Field(..., min_items=1, max_items=6)
    topic_hint: Optional[str] = Field(default="", max_length=400)
    max_papers_per_reviewer: int = Field(default=5, ge=1, le=10)
    mode: str = Field(default="medium")


class SavedPaper(BaseModel):
    material_id: str
    title: str
    source: str
    url: str
    doi: Optional[str]
    year: Optional[int]
    saved_at: str


class SavePapersResponse(BaseModel):
    saved: int
    material_ids: List[str]


class ListSavedPapersResponse(BaseModel):
    papers: List[SavedPaper]
    total: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/debates/{debate_id}/literature/search",
    response_model=LiteratureSearchResponse,
)
async def search_academic_literature(
    debate_id: str,
    body: LiteratureSearchRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Search academic databases for papers relevant to the review session.

    Returns deduplicated, ranked results from all requested providers.
    Does NOT persist anything — call /literature/save to add papers to context.
    """
    # Verify debate exists and user has access
    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    sources = body.sources or ALL_SOURCES
    # Sanitise source list
    unknown = [s for s in sources if s not in ALL_SOURCES]
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown sources: {unknown}. Valid: {ALL_SOURCES}",
        )

    papers = await search_literature(
        query=body.query,
        sources=sources,
        max_per_source=body.max_per_source,
        max_total=body.max_total,
    )

    return LiteratureSearchResponse(
        query=body.query,
        papers=[PaperResult(**p.to_dict()) for p in papers],
        total=len(papers),
        sources_queried=sources,
    )


@router.post(
    "/debates/{debate_id}/literature/save",
    response_model=SavePapersResponse,
)
async def save_papers_to_context(
    debate_id: str,
    body: SavePapersRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """
    Persist selected papers into the review session's RAG context.

    Each paper is stored as a meeting_material (kind='literature') and its
    abstract is chunked into memory_chunks so it will be retrieved during
    reviewer prep packs and turn context.
    """
    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    workspace_id = debate["workspace_id"]

    # Paywall: saved papers count toward the per-session material cap.
    from ..services.plans import require_material_quota
    require_material_quota(debate_id, str(workspace_id), len(body.papers))

    material_ids: List[str] = []

    try:
        with get_db_connection() as conn:
            cursor = get_cursor(conn)

            for paper_data in body.papers:
                material_id = str(uuid.uuid4())
                chunk_text = paper_to_chunk_text(
                    Paper(
                        title=paper_data.title,
                        authors=paper_data.authors,
                        year=paper_data.year,
                        abstract=paper_data.abstract,
                        url=paper_data.url,
                        doi=paper_data.doi,
                        venue=paper_data.venue,
                        citation_count=paper_data.citation_count,
                        source=paper_data.source,
                    )
                )

                # Insert into meeting_materials using the correct schema columns:
                # body_text stores the full paper chunk; url stores the paper link.
                cursor.execute(
                    """
                    INSERT INTO meeting_materials (
                        material_id, debate_id, kind, title,
                        body_text, url, processed_status, processing_metadata, created_at, updated_at
                    ) VALUES (
                        %s, %s, 'literature', %s,
                        %s, %s, 'complete', %s, NOW(), NOW()
                    )
                    ON CONFLICT (material_id) DO NOTHING
                    """,
                    (
                        material_id,
                        debate_id,
                        paper_data.title[:255],
                        chunk_text,
                        paper_data.url or None,
                        Json({
                            "source": paper_data.source,
                            "doi": paper_data.doi,
                            "year": paper_data.year,
                            "authors": paper_data.authors,
                            "venue": paper_data.venue,
                            "citation_count": paper_data.citation_count,
                            "label": body.label,
                            "saved_by": "literature_search",
                        }),
                    ),
                )

                # Insert abstract as a memory chunk for semantic retrieval.
                # memory_chunks requires agent_id OR source_debate_id per ownership constraint.
                # Literature chunks are not agent-owned, so use source_debate_id = debate_id.
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
                            "source": paper_data.source,
                            "paper_title": paper_data.title,
                            "doi": paper_data.doi,
                            "year": paper_data.year,
                            "saved_by": "literature_search",
                        }),
                    ),
                )

                material_ids.append(material_id)

            conn.commit()
    except psycopg2.Error as exc:
        logger.error("Failed to save literature papers: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist papers to review context",
        )

    return SavePapersResponse(saved=len(material_ids), material_ids=material_ids)


@router.post("/debates/{debate_id}/committee-twins")
async def create_committee_twins(
    debate_id: str,
    body: CommitteeTwinRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Pillar 2 — build corpus-grounded twins of named real reviewers.

    Pulls each reviewer's actual publications, ingests them as retrievable
    corpus, and returns a twin persona specialised on that person's work."""
    service = DebateService()
    debate = service.get_debate(debate_id)
    if not debate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    try:
        return await build_committee_twins(
            debate_id=debate_id,
            reviewers=[r.dict() for r in body.reviewers],
            max_papers_per_reviewer=body.max_papers_per_reviewer,
            topic_hint=body.topic_hint or "",
            mode=body.mode,  # type: ignore[arg-type]
        )
    except Exception as exc:
        logger.exception("Committee twin build failed for %s", debate_id)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get(
    "/debates/{debate_id}/literature",
    response_model=ListSavedPapersResponse,
)
async def list_saved_papers(
    debate_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """List all literature papers saved to a review session's context."""
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
            WHERE debate_id = %s AND kind = 'literature'
            ORDER BY created_at DESC
            """,
            (debate_id,),
        )
        rows = cursor.fetchall()

    papers = []
    for row in rows:
        meta = row.get("processing_metadata") or {}
        papers.append(
            SavedPaper(
                material_id=str(row["material_id"]),
                title=row["title"] or "",
                source=meta.get("source", "unknown"),
                url=row["url"] or "",
                doi=meta.get("doi"),
                year=meta.get("year"),
                saved_at=row["created_at"].isoformat() if row["created_at"] else "",
            )
        )

    return ListSavedPapersResponse(papers=papers, total=len(papers))
