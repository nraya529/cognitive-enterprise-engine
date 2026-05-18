from __future__ import annotations

from ...logging_setup import get_logger
from ...models.leads import SearchResult
from ...services.tavily_client import domain_from_url, search_companies

log = get_logger(__name__)


def build_discovery_query(niche: str, geography: str) -> str:
    """Build the primary broad discovery query for a target market."""

    return (
        f"{niche} in {geography} company operations invoice logistics "
        "contact email business profile"
    )


def build_discovery_query_matrix(niche: str, geography: str) -> list[str]:
    """Decompose a broad market into exact phrases that expose B2B buying signals."""

    base = f"{niche} {geography}".strip()
    return [
        f"{base} operations manager contact email",
        f"{base} invoice processing accounting operations",
        f"{base} logistics back office document workflow",
        f"{base} company directory leadership email",
        f"{base} multi location service business operations",
    ]


async def discover(niche: str, geography: str, max_results: int) -> list[SearchResult]:
    """Search Tavily across a query matrix and deduplicate companies by domain."""

    query_matrix = build_discovery_query_matrix(niche, geography)
    raw_results: list[SearchResult] = []
    per_query_limit = max(1, min(max_results, 5))
    for query in query_matrix:
        raw_results.extend(await search_companies(query, max_results=per_query_limit))

    seen_domains: set[str] = set()
    deduped: list[SearchResult] = []
    for result in raw_results:
        domain = domain_from_url(str(result.url))
        if domain and domain in seen_domains:
            continue
        if domain:
            seen_domains.add(domain)
        deduped.append(result)
        if len(deduped) >= max_results:
            break

    log.info(
        "prospecting_discovery_complete",
        results=len(deduped),
        queries=len(query_matrix),
        niche=niche,
        geography=geography,
    )
    return deduped

