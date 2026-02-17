"""Web search tool using DuckDuckGo for the agent."""

from __future__ import annotations

import asyncio
from typing import Any


async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return formatted results.

    Returns a summary of search results with titles, URLs, and snippets.
    """
    try:
        results = await asyncio.get_event_loop().run_in_executor(
            None, _search_sync, query, max_results
        )
        if not results:
            return f"No results found for query: {query}"

        formatted: list[str] = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url = r.get("href", r.get("url", ""))
            snippet = r.get("body", r.get("snippet", ""))
            formatted.append(f"{i}. **{title}**\n   URL: {url}\n   {snippet}")

        return "\n\n".join(formatted)
    except Exception as e:
        return f"Search failed: {type(e).__name__}: {e}"


def _search_sync(query: str, max_results: int) -> list[dict[str, Any]]:
    """Synchronous DuckDuckGo search."""
    try:
        from duckduckgo_search import DDGS  # type: ignore[import-untyped]

        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return results
    except ImportError:
        # Fallback: use a simple HTTP request to DuckDuckGo Lite
        import json
        import urllib.parse
        import urllib.request

        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())

        results: list[dict[str, Any]] = []
        for topic in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic.get("Text", "")[:80],
                    "href": topic["FirstURL"],
                    "body": topic.get("Text", ""),
                })
        return results
