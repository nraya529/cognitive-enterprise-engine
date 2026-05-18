from __future__ import annotations

from pydantic import HttpUrl

from ...config import settings
from ...logging_setup import get_logger
from ...models.leads import DraftStatus, LeadProfile, LeadStatus, ProspectingRunRead, RunStatus
from ...services import storage
from ...services.tavily_client import domain_from_url
from .copywriter import draft_for_lead
from .discovery import discover
from .qualification import qualify_result

log = get_logger(__name__)


def _email_domain(email: str | None) -> str | None:
    if not email:
        return None
    return email.rsplit("@", 1)[-1].lower()


def _source_urls(primary_url: HttpUrl | None, extras: list[HttpUrl] | None = None) -> list[HttpUrl]:
    urls: list[HttpUrl] = []
    if primary_url is not None:
        urls.append(primary_url)
    if extras:
        urls.extend(extras)
    return urls


async def run_prospecting(run_id: int) -> ProspectingRunRead:
    """Run discovery, qualification, copywriting, and persistence for one run."""

    run = await storage.update_run(run_id, status=RunStatus.RUNNING)
    created_leads = 0
    qualified_leads = 0
    drafts_created = 0

    try:
        results = await discover(run.niche, run.geography, run.max_results)
        for result in results:
            qualified = await qualify_result(
                result,
                niche=run.niche,
                geography=run.geography,
                threshold=run.qualification_threshold,
            )
            domain = qualified.domain or domain_from_url(str(result.url))
            email = str(qualified.contact_email) if qualified.contact_email else None
            existing = await storage.find_lead_by_domain_or_email(domain, email)
            if existing is not None:
                log.info("lead_deduped", company=qualified.company_name, existing_id=existing.id)
                continue

            status = LeadStatus.QUALIFIED if qualified.is_qualified else LeadStatus.REJECTED
            if email is None and qualified.is_qualified:
                status = LeadStatus.SUPPRESSED
            if _email_domain(email) in settings.blocked_domain_set:
                status = LeadStatus.SUPPRESSED

            lead = await storage.create_lead(
                run_id,
                LeadProfile(
                    company_name=qualified.company_name,
                    domain=domain,
                    website_url=qualified.website_url or result.url,
                    contact_email=qualified.contact_email,
                    industry=qualified.industry,
                    geography=qualified.geography or run.geography,
                    profile_summary=qualified.profile_summary,
                    pain_points=qualified.pain_points,
                    source_urls=_source_urls(result.url),
                    revenue_indicators=qualified.revenue_indicators,
                    employee_indicators=qualified.employee_indicators,
                    qualification_score=qualified.qualification_score,
                    risk_score=max(0.0, 1.0 - qualified.qualification_score),
                    qualification_reason=qualified.qualification_reason,
                    status=status,
                ),
            )
            created_leads += 1

            if lead.status != LeadStatus.QUALIFIED:
                continue
            qualified_leads += 1

            draft = await draft_for_lead(lead)
            await storage.create_draft(draft)
            drafts_created += 1

        run = await storage.update_run(
            run_id,
            status=RunStatus.COMPLETED,
            created_leads=created_leads,
            qualified_leads=qualified_leads,
            drafts_created=drafts_created,
        )
        log.info(
            "prospecting_run_complete",
            run_id=run_id,
            created_leads=created_leads,
            qualified_leads=qualified_leads,
            drafts_created=drafts_created,
        )
        return run
    except Exception as exc:
        log.exception("prospecting_run_failed", run_id=run_id)
        return await storage.update_run(
            run_id,
            status=RunStatus.FAILED,
            error=str(exc),
            created_leads=created_leads,
            qualified_leads=qualified_leads,
            drafts_created=drafts_created,
        )


async def send_approved_draft(draft_id: int):
    from ...services.email_sender import send_approved_draft as deliver

    draft = await storage.get_draft(draft_id)
    if draft.status == DraftStatus.SENT:
        return draft
    try:
        return await deliver(draft)
    except Exception as exc:
        log.exception("approved_draft_send_failed", draft_id=draft_id)
        await storage.mark_draft_failed(draft_id, str(exc))
        raise

