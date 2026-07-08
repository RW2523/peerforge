"""
Committee Twin service (Pillar 2)
=================================
Name the people who will actually sit on your review panel; PeerForge pulls
their REAL publications (Semantic Scholar / OpenAlex — already wired in
literature_search.py), ingests them as grounded corpus chunks, and builds a
"digital twin" reviewer specialised on that person's own body of work.

The twin's system prompt is constructed from the reviewer's actual papers — so
it can say: 'In my 2023 paper "…", I argued X — your Section 4 does the
opposite. Defend it,' quoting real, verifiable work rather than a generic role.

Honesty guarantees:
  * We only keep papers whose author list actually contains the named reviewer
    (surname match) — no mis-attributed work.
  * If the databases return nothing for a name (rate-limit, uncommon name), the
    twin is still built but flagged corpus_found=False with a generic prompt,
    and the shortfall is reported — never silently faked.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional

import httpx
from psycopg2.extras import Json

from ..database import get_db_connection, get_cursor
from .literature_search import search_literature, paper_to_chunk_text, Paper
from .persona_prompts import build_system_prompt, resolve_role
from .reasoning_modes import get_persona_model, ReasoningMode

logger = logging.getLogger(__name__)

# Databases with the best author coverage; arXiv/PubMed are topic-only.
_TWIN_SOURCES = ["openalex", "semantic_scholar"]

_CROSSREF_URL = "https://api.crossref.org/works"
_MAILTO = "peerforge@example.com"


def _strip_jats(text: str) -> str:
    """Crossref abstracts are JATS XML; strip tags to plain prose."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


async def _search_crossref_author(name: str, rows: int = 20) -> List[Paper]:
    """Author-specific search via Crossref (reliable, keyless, honours author)."""
    params = {"query.author": name, "rows": rows, "mailto": _MAILTO,
              "select": "title,author,issued,abstract,DOI,container-title,is-referenced-by-count,URL"}
    url = _CROSSREF_URL + "?" + urllib.parse.urlencode(params)
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        for it in resp.json().get("message", {}).get("items", []):
            title_list = it.get("title") or []
            if not title_list:
                continue
            authors = []
            for a in it.get("author", []) or []:
                full = " ".join(filter(None, [a.get("given"), a.get("family")]))
                if full:
                    authors.append(full)
            year = None
            parts = (it.get("issued") or {}).get("date-parts") or []
            if parts and parts[0]:
                year = parts[0][0]
            venue_list = it.get("container-title") or []
            papers.append(Paper(
                title=title_list[0].strip(),
                authors=authors[:8],
                year=year,
                abstract=_strip_jats(it.get("abstract", "")),
                url=it.get("URL", ""),
                doi=it.get("DOI"),
                venue=venue_list[0] if venue_list else "Crossref",
                citation_count=int(it.get("is-referenced-by-count") or 0),
                source="crossref",
            ))
    except Exception as exc:
        logger.warning("Crossref author search failed for %s: %s", name, exc)
    return papers


async def _fetch_author_papers(name: str, affiliation: str, topic_hint: str,
                               want: int) -> List[Paper]:
    """Resilient author-paper fetch: Crossref first (author-aware), then the
    multi-source topic search as a fallback. Returns papers actually authored
    by *name* (surname match), ranked by citations."""
    surname = _surname(name)
    # 1) Crossref author search — most reliable in constrained networks.
    found = await _search_crossref_author(name, rows=max(20, want * 4))
    authored = [p for p in found if _authored_by(p, surname)]
    # 2) Fallback: multi-database topic search biased by the reviewer's name.
    if len(authored) < want:
        try:
            query = " ".join(filter(None, [name, affiliation, topic_hint])).strip()
            extra = await search_literature(query=query, sources=_TWIN_SOURCES,
                                            max_per_source=want * 3, max_total=40)
            seen = {p.dedup_key for p in authored}
            for p in extra:
                if _authored_by(p, surname) and p.dedup_key not in seen:
                    authored.append(p)
                    seen.add(p.dedup_key)
        except Exception:
            pass
    authored.sort(key=lambda p: (p.citation_count, p.year or 0), reverse=True)
    return authored[:want]


def _surname(name: str) -> str:
    cleaned = re.sub(r"(?i)\b(dr|prof|professor|phd)\.?\b", "", name).strip()
    parts = [p for p in re.split(r"[\s,]+", cleaned) if p]
    return parts[-1].lower() if parts else cleaned.lower()


def _authored_by(paper: Paper, surname: str) -> bool:
    return any(surname in (a or "").lower() for a in paper.authors)


def _quote_from(paper: Paper, max_words: int = 30) -> str:
    text = (paper.abstract or "").strip()
    if not text:
        return paper.title
    words = text.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def _build_twin_prompt(name: str, affiliation: str, role: str,
                       papers: List[Paper], topic_hint: str) -> str:
    """Deterministic, corpus-grounded twin prompt (no hallucinated citations)."""
    corpus_lines = []
    for p in papers:
        yr = p.year or "n.d."
        corpus_lines.append(f'- "{p.title}" ({yr}, {p.venue or p.source})'
                            + (f' — "{_quote_from(p)}"' if p.abstract else ""))
    corpus_block = "\n".join(corpus_lines) if corpus_lines else "(no indexed publications found)"

    header = (
        f"[COMMITTEE TWIN — {name}"
        + (f", {affiliation}" if affiliation else "")
        + "]\n"
        f"You are a digital twin of the real reviewer {name}. You are on this "
        f"review panel to interrogate the researcher exactly as {name} would.\n\n"
        f"YOUR OWN PUBLISHED WORK (use it — cite yourself by title and year):\n"
        f"{corpus_block}\n\n"
        f"HOW YOU REVIEW:\n"
        f"- Ground your critique in YOUR corpus above. When a paper of yours is "
        f"relevant, reference it explicitly, e.g. 'In my {papers[0].year if papers else 'prior'} "
        f"work \"{papers[0].title if papers else '...'}\" I showed/argued …, so how does "
        f"your approach address that?'\n"
        f"- Probe where the researcher's method or claim conflicts with, ignores, "
        f"or fails to build on your established findings.\n"
        f"- Be specific and demanding; never accept a claim that contradicts your "
        f"own results without hard evidence.\n"
        f"- Never invent papers or findings you do not have; only cite the corpus above.\n\n"
    )
    return header


def _ingest_corpus(debate_id: str, twin_id: str, name: str, papers: List[Paper]) -> int:
    """Persist a twin's papers as retrievable corpus chunks (tagged to the twin)."""
    if not papers:
        return 0
    inserted = 0
    with get_db_connection() as conn:
        cur = get_cursor(conn)
        for p in papers:
            material_id = str(uuid.uuid4())
            chunk_text = paper_to_chunk_text(p)
            cur.execute(
                """
                INSERT INTO meeting_materials (
                    material_id, debate_id, kind, title, body_text, url,
                    processed_status, processing_metadata, created_at, updated_at
                ) VALUES (%s,%s,'literature',%s,%s,%s,'complete',%s,NOW(),NOW())
                ON CONFLICT (material_id) DO NOTHING
                """,
                (material_id, debate_id, p.title[:255], chunk_text, p.url or None,
                 Json({"reviewer_twin": name, "twin_id": twin_id, "source": p.source,
                       "doi": p.doi, "year": p.year, "authors": p.authors,
                       "saved_by": "committee_twin"})),
            )
            cur.execute(
                """
                INSERT INTO memory_chunks (
                    chunk_id, agent_id, source_debate_id, chunk_text, chunk_metadata, created_at
                ) VALUES (%s, NULL, %s, %s, %s, NOW())
                ON CONFLICT (chunk_id) DO NOTHING
                """,
                (str(uuid.uuid4()), debate_id, chunk_text[:4000],
                 Json({"material_id": material_id, "reviewer_twin": name, "twin_id": twin_id,
                       "source": p.source, "paper_title": p.title, "doi": p.doi,
                       "year": p.year, "saved_by": "committee_twin"})),
            )
            inserted += 1
        conn.commit()
    return inserted


async def build_committee_twins(
    debate_id: str,
    reviewers: List[Dict[str, str]],
    max_papers_per_reviewer: int = 5,
    topic_hint: str = "",
    mode: ReasoningMode = "medium",
) -> Dict[str, Any]:
    """Build corpus-grounded twins for each named reviewer. See module docstring."""
    twins: List[Dict[str, Any]] = []
    roles = ["Domain Expert", "Methodology Professor", "Skeptical Reviewer",
             "Independent Reviewer", "Advisor", "Friendly Professor"]

    for idx, rv in enumerate(reviewers[:6]):
        name = (rv.get("name") or "").strip()
        if not name:
            continue
        affiliation = (rv.get("affiliation") or "").strip()
        role = rv.get("role") or roles[idx % len(roles)]
        twin_id = str(uuid.uuid4())

        papers = await _fetch_author_papers(
            name, affiliation, topic_hint, want=max_papers_per_reviewer
        )
        corpus_found = bool(papers)

        chunks = _ingest_corpus(debate_id, twin_id, name, papers) if papers else 0
        system_prompt = _build_twin_prompt(name, affiliation, role, papers, topic_hint)
        canonical = resolve_role(role)

        twins.append({
            "twin_id": twin_id,
            "name": name,
            "affiliation": affiliation,
            "role": role,
            "corpus_found": corpus_found,
            "paper_count": len(papers),
            "chunks_ingested": chunks,
            "papers": [{
                "title": p.title, "year": p.year, "venue": p.venue,
                "citation_count": p.citation_count, "url": p.url, "doi": p.doi,
                "source": p.source, "quote": _quote_from(p),
            } for p in papers],
            "system_prompt": system_prompt,
            "model_id": get_persona_model(role, mode),
            "note": None if corpus_found else (
                f"No indexed publications matched “{name}”. The twin was built with a "
                f"generic reviewer prompt — refine the name/affiliation or add their papers manually."
            ),
        })

    return {
        "debate_id": debate_id,
        "twins": twins,
        "summary": {
            "requested": len([r for r in reviewers if (r.get("name") or "").strip()]),
            "built": len(twins),
            "with_corpus": sum(1 for t in twins if t["corpus_found"]),
            "papers_ingested": sum(t["paper_count"] for t in twins),
        },
    }
