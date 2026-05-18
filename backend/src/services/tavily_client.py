from __future__ import annotations

from urllib.parse import urlparse

import httpx

from ..config import settings
from ..logging_setup import get_logger
from ..models.leads import SearchResult

log = get_logger(__name__)


def domain_from_url(url: str) -> str | None:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host or None


async def search_companies(query: str, max_results: int) -> list[SearchResult]:
    if not settings.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY is required to run prospecting searches")

    payload = {
        "api_key": settings.tavily_api_key,
        "query": query,
        "search_depth": settings.tavily_search_depth,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }
    timeout = httpx.Timeout(30.0, connect=10.0)
    try:
        async with httpx.AsyncClient(base_url=settings.tavily_base_url, timeout=timeout) as client:
            response = await client.post("/search", json=payload)
            response.raise_for_status()
            body = response.json()
    except httpx.HTTPError as exc:
        log.warning("tavily_search_failed", query=query, error=str(exc))
        return []

    results: list[SearchResult] = []
    for item in body.get("results", []):
        try:
            results.append(
                SearchResult(
                    title=item.get("title") or "Untitled result",
                    url=item["url"],
                    content=item.get("content") or "",
                    score=float(item.get("score") or 0.0),
                )
            )
        except (KeyError, ValueError) as exc:
            log.warning("tavily_result_skipped", error=str(exc))

    log.info("tavily_search_complete", query=query, result_count=len(results))
    return results
