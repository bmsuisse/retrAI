"""Dataset fetching tool — retrieve data from public scientific APIs."""

from __future__ import annotations

import asyncio
import json
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# Max download size for arbitrary URLs (10 MB)
MAX_DOWNLOAD_BYTES = 10 * 1024 * 1024

# Trusted scientific domains for URL fetching
TRUSTED_DOMAINS: frozenset[str] = frozenset({
    "ncbi.nlm.nih.gov",
    "eutils.ncbi.nlm.nih.gov",
    "arxiv.org",
    "export.arxiv.org",
    "huggingface.co",
    "raw.githubusercontent.com",
    "data.gov",
    "zenodo.org",
    "figshare.com",
    "kaggle.com",
    "datadryad.org",
    "openalex.org",
    "api.openalex.org",
    "api.semanticscholar.org",
    "api.crossref.org",
})


@dataclass
class FetchResult:
    """Result of a dataset fetch operation."""

    source: str
    query: str
    total_results: int
    items: list[dict[str, Any]]
    error: str | None = None


async def _http_get(url: str, timeout: float = 30.0) -> tuple[str, int]:
    """Perform an async HTTP GET. Returns (body, status_code)."""
    proc = await asyncio.create_subprocess_exec(
        "curl", "-sS", "-L",
        "--max-time", str(int(timeout)),
        "--max-filesize", str(MAX_DOWNLOAD_BYTES),
        "-H", "Accept: application/json",
        "-w", "\n__STATUS__%{http_code}",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=timeout + 5,
        )
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return "", 0

    raw = stdout_bytes.decode("utf-8", errors="replace")
    # Extract status code
    if "__STATUS__" in raw:
        parts = raw.rsplit("__STATUS__", 1)
        body = parts[0]
        try:
            status = int(parts[1].strip())
        except ValueError:
            status = 0
    else:
        body = raw
        status = 200

    return body, status


async def _http_get_xml(url: str, timeout: float = 30.0) -> tuple[str, int]:
    """HTTP GET expecting XML response."""
    proc = await asyncio.create_subprocess_exec(
        "curl", "-sS", "-L",
        "--max-time", str(int(timeout)),
        "-H", "Accept: application/xml",
        "-w", "\n__STATUS__%{http_code}",
        url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_bytes, _ = await asyncio.wait_for(
            proc.communicate(), timeout=timeout + 5,
        )
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        return "", 0

    raw = stdout_bytes.decode("utf-8", errors="replace")
    if "__STATUS__" in raw:
        parts = raw.rsplit("__STATUS__", 1)
        body = parts[0]
        try:
            status = int(parts[1].strip())
        except ValueError:
            status = 0
    else:
        body = raw
        status = 200

    return body, status


async def search_pubmed(
    query: str,
    max_results: int = 10,
) -> FetchResult:
    """Search PubMed for biomedical literature."""
    encoded_query = quote_plus(query)

    # Step 1: Search for IDs
    search_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={encoded_query}&retmax={max_results}&retmode=json"
    )
    body, status = await _http_get(search_url)
    if status != 200:
        return FetchResult(
            source="pubmed", query=query, total_results=0, items=[],
            error=f"PubMed search failed (HTTP {status})",
        )

    try:
        data = json.loads(body)
        id_list = data.get("esearchresult", {}).get("idlist", [])
        total = int(data.get("esearchresult", {}).get("count", 0))
    except (json.JSONDecodeError, KeyError, ValueError):
        return FetchResult(
            source="pubmed", query=query, total_results=0, items=[],
            error="Failed to parse PubMed search results",
        )

    if not id_list:
        return FetchResult(source="pubmed", query=query, total_results=total, items=[])

    # Step 2: Fetch summaries
    ids_str = ",".join(id_list)
    summary_url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        f"?db=pubmed&id={ids_str}&retmode=json"
    )
    body, status = await _http_get(summary_url)
    if status != 200:
        return FetchResult(
            source="pubmed", query=query, total_results=total, items=[],
            error=f"PubMed summary fetch failed (HTTP {status})",
        )

    items: list[dict[str, Any]] = []
    try:
        data = json.loads(body)
        result_data = data.get("result", {})
        for pmid in id_list:
            article = result_data.get(pmid, {})
            if not isinstance(article, dict):
                continue
            authors = [
                a.get("name", "")
                for a in article.get("authors", [])
                if isinstance(a, dict)
            ]
            items.append({
                "pmid": pmid,
                "title": article.get("title", ""),
                "authors": authors[:5],
                "journal": article.get("fulljournalname", ""),
                "pub_date": article.get("pubdate", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
    except (json.JSONDecodeError, KeyError):
        return FetchResult(
            source="pubmed", query=query, total_results=total, items=[],
            error="Failed to parse PubMed summaries",
        )

    return FetchResult(source="pubmed", query=query, total_results=total, items=items)


async def search_arxiv(
    query: str,
    max_results: int = 10,
) -> FetchResult:
    """Search arXiv for research papers."""
    encoded_query = quote_plus(query)
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query=all:{encoded_query}&start=0&max_results={max_results}"
    )
    body, status = await _http_get_xml(url)
    if status != 200:
        return FetchResult(
            source="arxiv", query=query, total_results=0, items=[],
            error=f"arXiv search failed (HTTP {status})",
        )

    items: list[dict[str, Any]] = []
    total = 0
    try:
        root = ET.fromstring(body)
        ns = {"atom": "http://www.w3.org/2005/Atom", "opensearch": "http://a9.com/-/spec/opensearch/1.1/"}
        total_el = root.find("opensearch:totalResults", ns)
        if total_el is not None and total_el.text:
            total = int(total_el.text)

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)

            authors = []
            for author in entry.findall("atom:author", ns):
                name_el = author.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append(name_el.text)

            # Get categories
            categories = []
            for cat in entry.findall("atom:category", ns):
                term = cat.get("term", "")
                if term:
                    categories.append(term)

            items.append({
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "abstract": (summary_el.text or "").strip()[:500] if summary_el is not None else "",
                "authors": authors[:5],
                "published": (published_el.text or "") if published_el is not None else "",
                "categories": categories[:5],
                "url": (id_el.text or "") if id_el is not None else "",
            })
    except ET.ParseError:
        return FetchResult(
            source="arxiv", query=query, total_results=0, items=[],
            error="Failed to parse arXiv XML response",
        )

    return FetchResult(source="arxiv", query=query, total_results=total, items=items)


async def search_huggingface(
    query: str,
    max_results: int = 10,
) -> FetchResult:
    """Search HuggingFace Datasets for ML datasets."""
    encoded_query = quote_plus(query)
    url = (
        f"https://huggingface.co/api/datasets"
        f"?search={encoded_query}&limit={max_results}&sort=downloads&direction=-1"
    )
    body, status = await _http_get(url)
    if status != 200:
        return FetchResult(
            source="huggingface", query=query, total_results=0, items=[],
            error=f"HuggingFace API failed (HTTP {status})",
        )

    items: list[dict[str, Any]] = []
    try:
        datasets = json.loads(body)
        if not isinstance(datasets, list):
            datasets = []

        for ds in datasets[:max_results]:
            items.append({
                "id": ds.get("id", ""),
                "description": (ds.get("description", "") or "")[:300],
                "downloads": ds.get("downloads", 0),
                "likes": ds.get("likes", 0),
                "tags": ds.get("tags", [])[:10],
                "url": f"https://huggingface.co/datasets/{ds.get('id', '')}",
            })
    except (json.JSONDecodeError, KeyError):
        return FetchResult(
            source="huggingface", query=query, total_results=0, items=[],
            error="Failed to parse HuggingFace response",
        )

    return FetchResult(
        source="huggingface", query=query, total_results=len(items), items=items,
    )


async def fetch_url(
    url: str,
    save_path: str | None = None,
    cwd: str = ".",
) -> FetchResult:
    """Fetch data from a URL (with domain safety checks)."""
    from pathlib import Path
    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.hostname or ""

    # Check domain allowlist
    is_trusted = any(domain.endswith(d) for d in TRUSTED_DOMAINS)
    if not is_trusted:
        return FetchResult(
            source="url", query=url, total_results=0, items=[],
            error=(
                f"Domain '{domain}' is not in the trusted domains list. "
                f"Trusted: {', '.join(sorted(TRUSTED_DOMAINS)[:5])}..."
            ),
        )

    body, status = await _http_get(url, timeout=60.0)
    if status != 200:
        return FetchResult(
            source="url", query=url, total_results=0, items=[],
            error=f"URL fetch failed (HTTP {status})",
        )

    # Try to save if path provided
    if save_path:
        out_path = Path(cwd) / save_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
        return FetchResult(
            source="url", query=url, total_results=1,
            items=[{"saved_to": str(out_path), "size_bytes": len(body.encode())}],
        )

    # Return preview
    return FetchResult(
        source="url", query=url, total_results=1,
        items=[{"content_preview": body[:2000], "size_bytes": len(body.encode())}],
    )


async def dataset_fetch(
    source: str,
    query: str,
    max_results: int = 10,
    save_path: str | None = None,
    cwd: str = ".",
) -> str:
    """Fetch datasets from a scientific source.

    Args:
        source: One of "pubmed", "arxiv", "huggingface", "url".
        query: Search query or URL (if source=="url").
        max_results: Maximum results to return.
        save_path: Optional path to save downloaded data.
        cwd: Working directory for file operations.

    Returns:
        JSON string with results.
    """
    source = source.lower().strip()
    max_results = min(max_results, 50)  # Cap at 50

    if source == "pubmed":
        result = await search_pubmed(query, max_results)
    elif source == "arxiv":
        result = await search_arxiv(query, max_results)
    elif source in ("huggingface", "hf"):
        result = await search_huggingface(query, max_results)
    elif source == "url":
        result = await fetch_url(query, save_path, cwd)
    else:
        result = FetchResult(
            source=source, query=query, total_results=0, items=[],
            error=f"Unknown source '{source}'. Use: pubmed, arxiv, huggingface, url",
        )

    output: dict[str, Any] = {
        "source": result.source,
        "query": result.query,
        "total_results": result.total_results,
        "returned": len(result.items),
        "items": result.items,
    }
    if result.error:
        output["error"] = result.error

    return json.dumps(output, indent=2, default=str)
