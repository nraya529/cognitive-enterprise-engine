from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from src.config import settings
from src.main import app
from src.models.leads import SearchResult
from src.services import storage


def test_full_prospecting_pipeline_with_mocked_providers():
    asyncio.run(storage.close_storage())
    settings.database_url = "sqlite+aiosqlite:///:memory:"
    settings.tavily_api_key = "tvly-test"
    settings.resend_api_key = "re-test"
    settings.outbound_blocked_domains = "gmail.com,yahoo.com,hotmail.com"

    qualification_payload = {
        "company_name": "Acme Freight Systems",
        "domain": "acmefreight.example",
        "website_url": "https://acmefreight.example",
        "contact_email": "ops@acmefreight.example",
        "industry": "regional logistics",
        "geography": "New England",
        "profile_summary": "Regional freight company with visible document-heavy operations.",
        "pain_points": ["manual invoice reconciliation", "paperwork-heavy dispatch workflows"],
        "revenue_indicators": ["multi-region freight lanes"],
        "employee_indicators": ["operations leadership listed publicly"],
        "qualification_score": 0.86,
        "qualification_reason": "Operational complexity and B2B workflow volume are visible.",
        "is_qualified": True,
    }
    copy_payload = {
        "subject": "Reducing invoice reconciliation at Acme Freight Systems",
        "body": (
            "Hi,\n\nI noticed Acme Freight Systems appears to run paperwork-heavy freight "
            "operations across New England. We turn messy inbox documents and invoices into "
            "validated accounting-ready records before anyone re-keys them.\n\n"
            "If this is not relevant, reply no and I will not follow up."
        ),
    }

    async def fake_search(query: str, max_results: int):
        return [
            SearchResult(
                title="Acme Freight Systems",
                url="https://acmefreight.example",
                content="Contact ops@acmefreight.example for operations. Regional freight.",
                score=0.91,
            )
        ]

    with (
        patch(
            "src.agents.prospecting.discovery.search_companies",
            new=AsyncMock(side_effect=fake_search),
        ),
        patch(
            "src.agents.prospecting.qualification.call_text",
            new=AsyncMock(return_value=json.dumps(qualification_payload)),
        ),
        patch(
            "src.agents.prospecting.copywriter.call_text",
            new=AsyncMock(return_value=json.dumps(copy_payload)),
        ),
        patch(
            "src.services.email_sender._post_to_resend",
            new=AsyncMock(return_value="resend_msg_test"),
        ),
        TestClient(app) as client,
    ):
        response = client.post(
            "/prospecting/runs",
            json={
                "niche": "regional logistics",
                "geography": "New England",
                "max_results": 1,
                "qualification_threshold": 0.7,
            },
        )
        assert response.status_code == 202

        leads = client.get("/prospecting/leads").json()
        assert len(leads) == 1
        assert leads[0]["company_name"] == "Acme Freight Systems"
        assert leads[0]["qualification_score"] == 0.86

        drafts = client.get("/prospecting/drafts").json()
        assert len(drafts) == 1
        draft_id = drafts[0]["id"]
        assert drafts[0]["is_approved"] is False

        approved = client.post(
            f"/prospecting/drafts/{draft_id}/approve",
            json={"approved_by": "Test Operator"},
        )
        assert approved.status_code == 200
        assert approved.json()["is_approved"] is True

        sent = client.post(f"/prospecting/drafts/{draft_id}/send")
        assert sent.status_code == 200
        assert sent.json()["resend_message_id"] == "resend_msg_test"

    asyncio.run(storage.close_storage())
