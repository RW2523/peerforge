"""
PeerForge — Literature Search Service

Unified async interface for querying academic paper databases:
  - arXiv          (Atom API — no key required)
  - Semantic Scholar (Graph API — optional key via SEMANTIC_SCHOLAR_API_KEY)
  - PubMed / NCBI  (E-utilities — no key required)
  - Crossref       (REST API — no key required)
  - OpenAlex       (REST API — no key required)

All providers return a list of Paper objects; results are deduplicated by DOI
(falling back to normalised title) and ranked by relevance + citation count.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Paper:
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    abstract: str = ""
    url: str = ""
    doi: Optional[str] = None
    venue: str = ""
    citation_count: int = 0
    source: str = ""          # arxiv | semantic_scholar | pubmed | crossref | openalex

    @property
    def dedup_key(self) -> str:
        """Stable dedup key: DOI if available, else normalised title hash."""
        if self.doi:
            return f"doi:{self.doi.lower().strip()}"
        normalised = re.sub(r"[^a-z0-9]", "", self.title.lower())
        return f"title:{hashlib.md5(normalised.encode()).hexdigest()[:16]}"

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "abstract": self.abstract,
            "url": self.url,
            "doi": self.doi,
            "venue": self.venue,
            "citation_count": self.citation_count,
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Individual providers
# ---------------------------------------------------------------------------

_TIMEOUT = httpx.Timeout(15.0)


async def _search_arxiv(query: str, max_results: int = 10) -> List[Paper]:
    """Query arXiv Atom API."""
    # Note: pass query as plain string to urlencode — it handles encoding once.
    # Do NOT call urllib.parse.quote() first (would cause double-encoding).
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    url = "https://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            abstract_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)
            authors = [
                a.find("atom:name", ns).text or ""
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ]
            doi_el = entry.find("arxiv:doi", ns)
            year = None
            if published_el is not None and published_el.text:
                try:
                    year = int(published_el.text[:4])
                except ValueError:
                    pass
            arxiv_url = id_el.text.strip() if id_el is not None else ""
            papers.append(
                Paper(
                    title=(title_el.text or "").strip().replace("\n", " "),
                    authors=authors[:5],
                    year=year,
                    abstract=(abstract_el.text or "").strip().replace("\n", " "),
                    url=arxiv_url,
                    doi=doi_el.text.strip() if doi_el is not None else None,
                    venue="arXiv",
                    source="arxiv",
                )
            )
    except Exception as exc:
        logger.warning("arXiv search failed: %s", exc)
    return papers


async def _search_semantic_scholar(query: str, max_results: int = 10) -> List[Paper]:
    """Query Semantic Scholar Graph API v1."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    headers: dict = {
        "Accept": "application/json",
    }
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key
    params = {
        "query": query,
        "limit": max_results,
        "fields": "title,authors,year,abstract,externalIds,venue,citationCount,url",
    }
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        data = resp.json()
        for item in data.get("data", []):
            ext_ids = item.get("externalIds") or {}
            doi = ext_ids.get("DOI")
            paper_url = item.get("url") or (
                f"https://www.semanticscholar.org/paper/{item.get('paperId', '')}"
            )
            authors = [
                a.get("name", "") for a in (item.get("authors") or [])[:5]
            ]
            papers.append(
                Paper(
                    title=(item.get("title") or "").strip(),
                    authors=authors,
                    year=item.get("year"),
                    abstract=(item.get("abstract") or "").strip(),
                    url=paper_url,
                    doi=doi,
                    venue=item.get("venue") or "Semantic Scholar",
                    citation_count=item.get("citationCount") or 0,
                    source="semantic_scholar",
                )
            )
    except Exception as exc:
        logger.warning("Semantic Scholar search failed: %s", exc)
    return papers


async def _search_pubmed(query: str, max_results: int = 10) -> List[Paper]:
    """Query PubMed via NCBI E-utilities (esearch + efetch)."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            search_resp = await client.get(
                f"{base}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": query,
                    "retmax": max_results,
                    "retmode": "json",
                    "sort": "relevance",
                },
            )
            search_resp.raise_for_status()
            ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return []

            fetch_resp = await client.get(
                f"{base}/efetch.fcgi",
                params={
                    "db": "pubmed",
                    "id": ",".join(ids),
                    "retmode": "xml",
                    "rettype": "abstract",
                },
            )
            fetch_resp.raise_for_status()

        root = ET.fromstring(fetch_resp.text)
        for article in root.findall(".//PubmedArticle"):
            medline = article.find("MedlineCitation")
            if medline is None:
                continue
            art = medline.find("Article")
            if art is None:
                continue
            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""
            abstract_texts = art.findall(".//AbstractText")
            abstract = " ".join(
                "".join(el.itertext()) for el in abstract_texts
            ).strip()
            # Year
            year = None
            pub_date = art.find(".//PubDate")
            if pub_date is not None:
                year_el = pub_date.find("Year")
                if year_el is not None and year_el.text:
                    try:
                        year = int(year_el.text)
                    except ValueError:
                        pass
            # Authors
            authors = []
            for author in art.findall(".//Author")[:5]:
                last = author.findtext("LastName") or ""
                first = author.findtext("ForeName") or ""
                if last:
                    authors.append(f"{last}, {first}".strip(", "))
            # DOI
            doi = None
            for id_el in article.findall(".//ArticleId"):
                if id_el.attrib.get("IdType") == "doi":
                    doi = id_el.text
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else ""
            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else ""
            journal_el = art.find(".//Journal/Title")
            venue = journal_el.text if journal_el is not None else "PubMed"
            papers.append(
                Paper(
                    title=title.strip(),
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    url=url,
                    doi=doi,
                    venue=venue,
                    source="pubmed",
                )
            )
    except Exception as exc:
        logger.warning("PubMed search failed: %s", exc)
    return papers


async def _search_crossref(query: str, max_results: int = 10) -> List[Paper]:
    """Query Crossref REST API."""
    url = "https://api.crossref.org/works"
    params = {
        "query": query,
        "rows": max_results,
        "select": "title,author,published,DOI,abstract,container-title,is-referenced-by-count,URL",
    }
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                url,
                params=params,
                headers={"User-Agent": "PeerForge/1.0 (mailto:peerforge@example.com)"},
            )
            resp.raise_for_status()
        items = resp.json().get("message", {}).get("items", [])
        for item in items:
            title_list = item.get("title") or []
            title = title_list[0] if title_list else ""
            authors = []
            for a in (item.get("author") or [])[:5]:
                family = a.get("family", "")
                given = a.get("given", "")
                if family:
                    authors.append(f"{family}, {given}".strip(", "))
            year = None
            pub = item.get("published") or item.get("published-print") or {}
            date_parts = pub.get("date-parts", [[]])[0] if pub else []
            if date_parts:
                try:
                    year = int(date_parts[0])
                except (ValueError, IndexError):
                    pass
            doi = item.get("DOI")
            paper_url = item.get("URL") or (f"https://doi.org/{doi}" if doi else "")
            venue_list = item.get("container-title") or []
            venue = venue_list[0] if venue_list else "Crossref"
            abstract = item.get("abstract") or ""
            # Strip JATS XML tags from abstract
            abstract = re.sub(r"<[^>]+>", " ", abstract).strip()
            papers.append(
                Paper(
                    title=title.strip(),
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    url=paper_url,
                    doi=doi,
                    venue=venue,
                    citation_count=item.get("is-referenced-by-count") or 0,
                    source="crossref",
                )
            )
    except Exception as exc:
        logger.warning("Crossref search failed: %s", exc)
    return papers


async def _search_openalex(query: str, max_results: int = 10) -> List[Paper]:
    """Query OpenAlex Works API."""
    url = "https://api.openalex.org/works"
    params = {
        "search": query,
        "per-page": max_results,
        "select": "title,authorships,publication_year,abstract_inverted_index,primary_location,ids,cited_by_count",
        "mailto": "peerforge@example.com",
    }
    papers: List[Paper] = []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
        results = resp.json().get("results", [])
        for item in results:
            title = (item.get("title") or "").strip()
            authors = []
            for auth in (item.get("authorships") or [])[:5]:
                author_obj = auth.get("author") or {}
                name = author_obj.get("display_name", "")
                if name:
                    authors.append(name)
            year = item.get("publication_year")
            # Reconstruct abstract from inverted index
            inv_index = item.get("abstract_inverted_index") or {}
            abstract = _reconstruct_abstract(inv_index)
            ids = item.get("ids") or {}
            doi = ids.get("doi", "").replace("https://doi.org/", "") or None
            location = item.get("primary_location") or {}
            source_obj = location.get("source") or {}
            venue = source_obj.get("display_name") or "OpenAlex"
            paper_url = ids.get("openalex") or (f"https://doi.org/{doi}" if doi else "")
            papers.append(
                Paper(
                    title=title,
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    url=paper_url,
                    doi=doi if doi else None,
                    venue=venue,
                    citation_count=item.get("cited_by_count") or 0,
                    source="openalex",
                )
            )
    except Exception as exc:
        logger.warning("OpenAlex search failed: %s", exc)
    return papers


def _reconstruct_abstract(inv_index: dict) -> str:
    """Reconstruct an abstract string from OpenAlex inverted-index format."""
    if not inv_index:
        return ""
    position_word: dict[int, str] = {}
    for word, positions in inv_index.items():
        for pos in positions:
            position_word[pos] = word
    return " ".join(position_word[i] for i in sorted(position_word))


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

PROVIDER_MAP = {
    "arxiv": _search_arxiv,
    "semantic_scholar": _search_semantic_scholar,
    "pubmed": _search_pubmed,
    "crossref": _search_crossref,
    "openalex": _search_openalex,
}

ALL_SOURCES = list(PROVIDER_MAP.keys())


def _condense_query(query: str, max_chars: int = 300) -> str:
    """
    Turn a long prose research question into a concise keyword search string.

    Strategy:
    1. Take only the first sentence / line (captures the core topic).
    2. Strip common filler phrases that confuse API keyword search.
    3. Hard-truncate to max_chars so every external API call stays well within limits.
    """
    # Use the first non-empty line (handles multi-paragraph problem statements)
    first_line = next(
        (ln.strip() for ln in query.splitlines() if ln.strip()),
        query,
    )
    # Drop leading question labels like "Main Research Question"
    first_line = re.sub(
        r"^(main\s+)?research\s+question[:\s]*",
        "",
        first_line,
        flags=re.IGNORECASE,
    ).strip()
    # Remove filler words that hurt keyword search quality
    filler = r"\b(how can|how do|what is|what are|can we|whether|using|based on|in order to)\b"
    condensed = re.sub(filler, " ", first_line, flags=re.IGNORECASE)
    condensed = re.sub(r"\s{2,}", " ", condensed).strip()
    return condensed[:max_chars]


async def search_literature(
    query: str,
    sources: Optional[List[str]] = None,
    max_per_source: int = 8,
    max_total: int = 30,
) -> List[Paper]:
    """
    Run parallel searches across the requested sources and return a
    deduplicated, ranked list of Paper objects.

    Args:
        query:           Free-text search query (may be long prose — will be condensed).
        sources:         List of source keys to query. Defaults to all.
        max_per_source:  Maximum results to request per provider.
        max_total:       Maximum total results to return after aggregation.

    Returns:
        Sorted list of Paper objects (most relevant / most cited first).
    """
    if sources is None:
        sources = ALL_SOURCES

    # Condense long prose queries into concise keyword strings for external APIs
    search_query = _condense_query(query) if len(query) > 200 else query
    if search_query != query:
        logger.info("Query condensed from %d chars to %d chars: %r",
                    len(query), len(search_query), search_query)

    tasks = [
        PROVIDER_MAP[src](search_query, max_per_source)
        for src in sources
        if src in PROVIDER_MAP
    ]
    raw_results: list[list[Paper]] = await asyncio.gather(*tasks, return_exceptions=True)

    # Flatten, skipping exception results
    all_papers: List[Paper] = []
    for batch in raw_results:
        if isinstance(batch, list):
            all_papers.extend(batch)

    # Deduplicate by dedup_key (keep highest citation_count duplicate)
    seen: dict[str, Paper] = {}
    for paper in all_papers:
        key = paper.dedup_key
        if key not in seen or paper.citation_count > seen[key].citation_count:
            seen[key] = paper

    # Filter out papers with empty titles
    unique = [p for p in seen.values() if p.title.strip()]

    # Rank: primary sort by citation count desc, secondary by recency desc
    unique.sort(
        key=lambda p: (p.citation_count, p.year or 0),
        reverse=True,
    )

    return unique[:max_total]


def paper_to_chunk_text(paper: Paper) -> str:
    """Format a Paper as a text chunk suitable for RAG ingestion."""
    authors_str = "; ".join(paper.authors) if paper.authors else "Unknown authors"
    year_str = str(paper.year) if paper.year else "n.d."
    lines = [
        f"TITLE: {paper.title}",
        f"AUTHORS: {authors_str}",
        f"YEAR: {year_str}",
        f"VENUE: {paper.venue}",
        f"SOURCE: {paper.source.upper()}",
    ]
    if paper.doi:
        lines.append(f"DOI: {paper.doi}")
    if paper.url:
        lines.append(f"URL: {paper.url}")
    if paper.citation_count:
        lines.append(f"CITATIONS: {paper.citation_count}")
    if paper.abstract:
        lines.append(f"\nABSTRACT:\n{paper.abstract}")
    return "\n".join(lines)
