from __future__ import annotations

import json

from pydantic import ValidationError

from ...config import settings
from ...logging_setup import get_logger
from ...models.leads import DraftStatus, EmailDraftRead, LeadProfile
from ...services.anthropic_client import call_text
from .qualification import _strip_json

log = get_logger(__name__)

COPYWRITER_SYSTEM = """You are the outbound copywriter for an AI back-office automation product.

Write concise cold B2B email copy for an operations leader at a qualified company. The offer: an engine that turns messy emails, invoices, onboarding sheets, and operational logs into validated structured records for accounting and legacy workflows.

Return ONLY JSON with keys "subject" and "body".

Rules:
- Two to four short paragraphs.
- Reference one or two observable details from the lead profile.
- Tie the pain point to a specific automation outcome.
- Do not promise exact savings or claim a relationship.
- Include this final sentence exactly once: 'If this is not relevant, reply no and I will not follow up.'"""

OPT_OUT_LINE = "If this is not relevant, reply no and I will not follow up."


async def draft_for_lead(lead: LeadProfile) -> EmailDraftRead:
    """Generate an approval-gated outbound draft for a persisted lead."""

    if lead.id is None or lead.run_id is None:
        raise ValueError("lead must be persisted before drafting")
    if lead.contact_email is None:
        raise ValueError("lead must have a contact_email before drafting")

    context = {
        "company_name": lead.company_name,
        "domain": lead.domain,
        "website_url": str(lead.website_url) if lead.website_url else None,
        "industry": lead.industry,
        "geography": lead.geography,
        "profile_summary": lead.profile_summary,
        "pain_points": lead.pain_points,
        "revenue_indicators": lead.revenue_indicators,
        "employee_indicators": lead.employee_indicators,
        "qualification_score": lead.qualification_score,
        "qualification_reason": lead.qualification_reason,
    }
    raw = await call_text(
        model=settings.prospecting_model,
        system=COPYWRITER_SYSTEM,
        user_message=json.dumps(context, indent=2),
        max_tokens=1024,
        effort="medium",
    )
    try:
        parsed = json.loads(_strip_json(raw))
        subject = str(parsed["subject"]).strip()
        body = str(parsed["body"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
        log.warning("copywriter_parse_failed", lead_id=lead.id, error=str(exc))
        pain = lead.pain_points[0] if lead.pain_points else "manual document handling"
        subject = f"Reducing {pain} at {lead.company_name}"
        body = (
            f"Hi,\n\nI noticed {lead.company_name} runs operationally dense "
            f"{lead.industry or 'business'} workflows. We help teams turn messy inboxes, "
            "invoices, onboarding sheets, and logs into validated accounting-ready records "
            "without manual re-keying.\n\n"
            "If your team is still moving document data into spreadsheets or legacy systems "
            "by hand, I can share a focused example of how this would work for you.\n\n"
            f"{OPT_OUT_LINE}"
        )

    if OPT_OUT_LINE not in body:
        body = f"{body.rstrip()}\n\n{OPT_OUT_LINE}"

    draft = EmailDraftRead(
        run_id=lead.run_id,
        lead_id=lead.id,
        to_email=lead.contact_email,
        subject=subject[:160],
        body=body,
        body_html=body.replace("\n", "<br>\n"),
        status=DraftStatus.DRAFTED,
        is_approved=False,
    )
    log.info("outreach_draft_created", lead_id=lead.id, to_email=str(lead.contact_email))
    return draft

