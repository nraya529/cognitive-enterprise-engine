from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from ..config import settings
from ..db import Base, utcnow
from ..logging_setup import get_logger
from ..models.leads import (
    DraftStatus,
    EmailDraft,
    EmailDraftRead,
    Lead,
    LeadProfile,
    LeadStatus,
    ProspectingRun,
    ProspectingRunRead,
    ProspectingRunRequest,
    RunStatus,
    SuppressedRecipient,
)

log = get_logger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(settings.database_url, future=True)
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def init_storage() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("storage_initialized", database_url=settings.database_url)


async def close_storage() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


def _run_to_schema(record: ProspectingRun) -> ProspectingRunRead:
    return ProspectingRunRead(
        id=record.id,
        trace_id=record.trace_id,
        niche=record.niche,
        geography=record.geography,
        max_results=record.max_results,
        qualification_threshold=record.qualification_threshold,
        status=RunStatus(record.status),
        requested_at=record.requested_at,
        completed_at=record.completed_at,
        error=record.error,
        created_leads=record.created_leads,
        qualified_leads=record.qualified_leads,
        drafts_created=record.drafts_created,
    )


def _lead_to_schema(record: Lead) -> LeadProfile:
    enrichment = record.enrichment or {}
    return LeadProfile(
        id=record.id,
        run_id=record.run_id,
        company_name=record.company_name,
        domain=record.domain,
        website_url=record.website,
        contact_email=record.email,
        industry=record.industry,
        geography=record.geography,
        profile_summary=enrichment.get("profile_summary", ""),
        pain_points=enrichment.get("pain_points", []),
        source_urls=enrichment.get("source_urls", []),
        revenue_indicators=enrichment.get("revenue_indicators", []),
        employee_indicators=enrichment.get("employee_indicators", []),
        qualification_score=record.qualification_score,
        risk_score=record.risk_score,
        qualification_reason=enrichment.get("qualification_reason", ""),
        status=LeadStatus(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _draft_to_schema(record: EmailDraft) -> EmailDraftRead:
    return EmailDraftRead(
        id=record.id,
        run_id=record.run_id,
        lead_id=record.lead_id,
        to_email=record.to_email,
        subject=record.subject,
        body=record.body,
        body_html=record.body_html,
        status=DraftStatus(record.status),
        is_approved=record.is_approved,
        approved_at=record.approved_at,
        approved_by=record.approved_by,
        created_at=record.created_at,
        sent_at=record.sent_at,
        resend_message_id=record.resend_message_id,
        error=record.error,
        send_attempts=record.send_attempts,
    )


async def create_run(request: ProspectingRunRequest, trace_id: str) -> ProspectingRunRead:
    async with get_sessionmaker()() as session:
        record = ProspectingRun(
            trace_id=trace_id,
            niche=request.niche,
            geography=request.geography,
            max_results=request.max_results,
            qualification_threshold=request.qualification_threshold,
            status=RunStatus.QUEUED.value,
            requested_at=utcnow(),
        )
        session.add(record)
        await session.commit()
        return _run_to_schema(record)


async def get_run(run_id: int) -> ProspectingRunRead:
    async with get_sessionmaker()() as session:
        record = await session.get(ProspectingRun, run_id)
        if record is None:
            raise KeyError(f"prospecting run {run_id} not found")
        return _run_to_schema(record)


async def list_runs(limit: int = 25) -> list[ProspectingRunRead]:
    async with get_sessionmaker()() as session:
        rows = await session.scalars(
            select(ProspectingRun).order_by(ProspectingRun.requested_at.desc()).limit(limit)
        )
        return [_run_to_schema(r) for r in rows]


async def update_run(
    run_id: int,
    *,
    status: RunStatus | None = None,
    error: str | None = None,
    created_leads: int | None = None,
    qualified_leads: int | None = None,
    drafts_created: int | None = None,
) -> ProspectingRunRead:
    async with get_sessionmaker()() as session:
        record = await session.get(ProspectingRun, run_id)
        if record is None:
            raise KeyError(f"prospecting run {run_id} not found")
        if status is not None:
            record.status = status.value
            if status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                record.completed_at = utcnow()
        if error is not None:
            record.error = error
        if created_leads is not None:
            record.created_leads = created_leads
        if qualified_leads is not None:
            record.qualified_leads = qualified_leads
        if drafts_created is not None:
            record.drafts_created = drafts_created
        await session.commit()
        return _run_to_schema(record)


async def find_lead_by_domain_or_email(
    domain: str | None, email: str | None
) -> LeadProfile | None:
    if not domain and not email:
        return None
    conditions = []
    if domain:
        conditions.append(Lead.domain == domain)
    if email:
        conditions.append(Lead.email == email)
    async with get_sessionmaker()() as session:
        record = await session.scalar(select(Lead).where(or_(*conditions)))
        return _lead_to_schema(record) if record else None


async def create_lead(run_id: int, lead: LeadProfile) -> LeadProfile:
    now = utcnow()
    enrichment = {
        "profile_summary": lead.profile_summary,
        "pain_points": lead.pain_points,
        "source_urls": [str(u) for u in lead.source_urls],
        "revenue_indicators": lead.revenue_indicators,
        "employee_indicators": lead.employee_indicators,
        "qualification_reason": lead.qualification_reason,
    }
    async with get_sessionmaker()() as session:
        record = Lead(
            run_id=run_id,
            company_name=lead.company_name,
            email=str(lead.contact_email) if lead.contact_email else None,
            website=str(lead.website_url) if lead.website_url else None,
            domain=lead.domain,
            industry=lead.industry,
            geography=lead.geography,
            qualification_score=lead.qualification_score,
            risk_score=lead.risk_score,
            status=lead.status.value,
            enrichment=enrichment,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        await session.commit()
        return _lead_to_schema(record)


async def get_lead(lead_id: int) -> LeadProfile:
    async with get_sessionmaker()() as session:
        record = await session.get(Lead, lead_id)
        if record is None:
            raise KeyError(f"lead {lead_id} not found")
        return _lead_to_schema(record)


async def list_leads(
    run_id: int | None = None, status: LeadStatus | None = None
) -> list[LeadProfile]:
    stmt = select(Lead).order_by(Lead.created_at.desc())
    conditions = []
    if run_id is not None:
        conditions.append(Lead.run_id == run_id)
    if status is not None:
        conditions.append(Lead.status == status.value)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    async with get_sessionmaker()() as session:
        rows = await session.scalars(stmt)
        return [_lead_to_schema(r) for r in rows]


async def create_draft(draft: EmailDraftRead) -> EmailDraftRead:
    async with get_sessionmaker()() as session:
        record = EmailDraft(
            run_id=draft.run_id,
            lead_id=draft.lead_id,
            to_email=str(draft.to_email),
            subject=draft.subject,
            body=draft.body,
            body_html=draft.body_html,
            is_approved=False,
            status=DraftStatus.DRAFTED.value,
            send_attempts=0,
            created_at=utcnow(),
        )
        session.add(record)
        await session.commit()
        return _draft_to_schema(record)


async def get_draft(draft_id: int) -> EmailDraftRead:
    async with get_sessionmaker()() as session:
        record = await session.get(EmailDraft, draft_id)
        if record is None:
            raise KeyError(f"email draft {draft_id} not found")
        return _draft_to_schema(record)


async def list_drafts(
    run_id: int | None = None, status: DraftStatus | None = None
) -> list[EmailDraftRead]:
    stmt = select(EmailDraft).order_by(EmailDraft.created_at.desc())
    conditions = []
    if run_id is not None:
        conditions.append(EmailDraft.run_id == run_id)
    if status is not None:
        conditions.append(EmailDraft.status == status.value)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    async with get_sessionmaker()() as session:
        rows = await session.scalars(stmt)
        return [_draft_to_schema(r) for r in rows]


async def approve_draft(draft_id: int, approved_by: str) -> EmailDraftRead:
    async with get_sessionmaker()() as session:
        record = await session.get(EmailDraft, draft_id)
        if record is None:
            raise KeyError(f"email draft {draft_id} not found")
        record.status = DraftStatus.APPROVED.value
        record.is_approved = True
        record.approved_at = utcnow()
        record.approved_by = approved_by
        record.error = None
        await session.commit()
        return _draft_to_schema(record)


async def mark_draft_sent(draft_id: int, resend_message_id: str | None) -> EmailDraftRead:
    async with get_sessionmaker()() as session:
        record = await session.get(EmailDraft, draft_id)
        if record is None:
            raise KeyError(f"email draft {draft_id} not found")
        record.status = DraftStatus.SENT.value
        record.sent_at = utcnow()
        record.resend_message_id = resend_message_id
        record.error = None
        record.send_attempts = record.send_attempts + 1
        await session.commit()
        return _draft_to_schema(record)


async def mark_draft_failed(draft_id: int, error: str) -> EmailDraftRead:
    async with get_sessionmaker()() as session:
        record = await session.get(EmailDraft, draft_id)
        if record is None:
            raise KeyError(f"email draft {draft_id} not found")
        record.status = DraftStatus.FAILED.value
        record.error = error
        record.send_attempts = record.send_attempts + 1
        await session.commit()
        return _draft_to_schema(record)


async def add_suppressed_recipient(email: str, reason: str) -> None:
    normalized = email.lower().strip()
    async with get_sessionmaker()() as session:
        existing = await session.scalar(
            select(SuppressedRecipient).where(SuppressedRecipient.email == normalized)
        )
        if existing is not None:
            return
        session.add(SuppressedRecipient(email=normalized, reason=reason, created_at=utcnow()))
        await session.commit()


async def is_email_suppressed(email: str) -> bool:
    normalized = email.lower().strip()
    async with get_sessionmaker()() as session:
        suppressed = await session.scalar(
            select(SuppressedRecipient).where(SuppressedRecipient.email == normalized)
        )
        if suppressed is not None:
            return True
        already_sent = await session.scalar(
            select(EmailDraft).where(
                EmailDraft.to_email == normalized,
                EmailDraft.status == DraftStatus.SENT.value,
            )
        )
        return already_sent is not None


async def sent_count_for_run(run_id: int) -> int:
    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(EmailDraft)
            .where(
                EmailDraft.run_id == run_id,
                EmailDraft.status == DraftStatus.SENT.value,
            )
        )
    return int(count or 0)


async def sent_count_since(since: datetime) -> int:
    async with get_sessionmaker()() as session:
        count = await session.scalar(
            select(func.count())
            .select_from(EmailDraft)
            .where(
                EmailDraft.status == DraftStatus.SENT.value,
                EmailDraft.sent_at >= since,
            )
        )
    return int(count or 0)
