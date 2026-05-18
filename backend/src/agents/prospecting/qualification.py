from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ...config import settings
from ...logging_setup import get_logger
from ...models.leads import QualifiedLead, SearchResult
from ...services.anthropic_client import call_text
from ...services.tavily_client import domain_from_url

log = get_logger(__name__)

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)

QUALIFICATION_SYSTEM = """You are the B2B Qualification Agent for an AI back-office automation product.

Assess whether a company is a credible high-ticket prospect for a system that ingests messy operational documents, validates financial math, and posts structured outputs into legacy accounting workflows.

Return ONLY a JSON object with these keys:
company_name, domain, website_url, contact_email, industry, geography, profile_summary, pain_points, revenue_indicators, employee_indicators, qualification_score, qualification_reason, is_qualified.

Rules:
- qualification_score is 0.0 to 1.0.
- is_qualified should be true only for companies with evidence of meaningful operational volume, B2B workflows, regulated/admin burden, or multi-location/service complexity.
- contact_email must be a corporate email visible in the evidence, or null.
- Do not invent revenue, employee count, or email addresses. Use evidence-backed indicators only."""


def _strip_json(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json").strip()
    if text.startswith("```"):
        text = text.removeprefix("```").strip()
    if text.endswith("```"):
        text = text.removesuffix("```").strip()
    return text


def _first_email(text: str) -> str | None:
    match = EMAIL_RE.search(text)
    return match.group(0).lower() if match else None


async def qualify_result(
    result: SearchResult,
    *,
    niche: str,
    geography: str,
    threshold: float,
) -> QualifiedLead:
    domain = domain_from_url(str(result.url))
    visible_email = _first_email(result.content)
    context = {
        "target_niche": niche,
        "target_geography": geography,
        "result_title": result.title,
        "result_url": str(result.url),
        "result_domain": domain,
        "visible_email": visible_email,
        "result_content": result.content[:4000],
        "minimum_score": threshold,
    }
    raw = await call_text(
        model=settings.prospecting_model,
        system=QUALIFICATION_SYSTEM,
        user_message=json.dumps(context, indent=2),
        max_tokens=2048,
        effort="medium",
    )
    try:
        data = json.loads(_strip_json(raw))
        if not data.get("domain"):
            data["domain"] = domain
        if not data.get("website_url"):
            data["website_url"] = str(result.url)
        if not data.get("contact_email"):
            data["contact_email"] = visible_email
        data["is_qualified"] = bool(data.get("is_qualified")) and (
            float(data.get("qualification_score") or 0.0) >= threshold
        )
        lead = QualifiedLead(**data)
    except (json.JSONDecodeError, TypeError, ValueError, ValidationError) as exc:
        log.warning("qualification_parse_failed", error=str(exc), url=str(result.url))
        lead = QualifiedLead(
            company_name=result.title[:120],
            domain=domain,
            website_url=result.url,
            contact_email=visible_email,
            industry=niche,
            geography=geography,
            profile_summary=result.content[:500],
            pain_points=[],
            revenue_indicators=[],
            employee_indicators=[],
            qualification_score=0.0,
            qualification_reason=f"Unable to parse qualification response: {exc}",
            is_qualified=False,
        )

    log.info(
        "lead_qualified",
        company=lead.company_name,
        score=lead.qualification_score,
        is_qualified=lead.is_qualified,
    )
    return lead

