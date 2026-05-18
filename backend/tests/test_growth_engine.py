from __future__ import annotations

import asyncio

import pytest

from src.config import settings
from src.models.leads import (
    DraftApprovalRequest,
    DraftStatus,
    EmailDraftRead,
    LeadProfile,
    LeadStatus,
    ProspectingRunRequest,
)
from src.services import email_sender, storage


def run(coro):
    return asyncio.run(coro)


async def _fresh_storage(tmp_path):
    await storage.close_storage()
    settings.database_url = f"sqlite+aiosqlite:///{tmp_path / 'growth.db'}"
    await storage.init_storage()


def test_lead_schema_rejects_unknown_fields():
    with pytest.raises(ValueError):
        LeadProfile(company_name="Acme Logistics", unexpected=True)


def test_approval_request_requires_actor():
    with pytest.raises(ValueError):
        DraftApprovalRequest(approved_by="x")


def test_storage_run_lead_draft_roundtrip(tmp_path):
    async def scenario():
        await _fresh_storage(tmp_path)
        run_record = await storage.create_run(
            ProspectingRunRequest(
                niche="regional logistics",
                geography="New England",
                max_results=3,
                qualification_threshold=0.7,
            ),
            trace_id="trace123",
        )
        lead = await storage.create_lead(
            run_record.id,
            LeadProfile(
                company_name="Acme Logistics",
                domain="acmelogistics.example",
                website_url="https://acmelogistics.example",
                contact_email="ops@acmelogistics.example",
                industry="logistics",
                geography="New England",
                profile_summary="Regional freight operator with manual paperwork.",
                pain_points=["manual invoice reconciliation"],
                source_urls=["https://acmelogistics.example"],
                qualification_score=0.82,
                qualification_reason="Operational complexity is visible.",
                status=LeadStatus.QUALIFIED,
            ),
        )
        draft = await storage.create_draft(
            EmailDraftRead(
                run_id=run_record.id,
                lead_id=lead.id,
                to_email="ops@acmelogistics.example",
                subject="Reducing invoice re-keying",
                body="Short personalized email.",
            )
        )
        approved = await storage.approve_draft(draft.id, "Niketh")
        assert approved.status == DraftStatus.APPROVED
        assert approved.approved_by == "Niketh"
        await storage.close_storage()

    run(scenario())


def test_unapproved_draft_cannot_send():
    draft = EmailDraftRead(
        id=1,
        run_id=1,
        lead_id=1,
        to_email="ops@example.com",
        subject="Hello",
        body="Body",
        status=DraftStatus.DRAFTED,
    )
    with pytest.raises(PermissionError):
        run(email_sender.send_approved_draft(draft))

