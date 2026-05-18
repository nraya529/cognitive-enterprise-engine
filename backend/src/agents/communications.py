from __future__ import annotations

import json

from ..config import settings
from ..logging_setup import get_logger
from ..models.schemas import ProcessedDocument, ReviewReason
from ..services.anthropic_client import call_text

log = get_logger(__name__)


COMMUNICATIONS_SYSTEM = """You are the Autonomous Communications Agent for an SMB back-office automation system.

Your function: given a structured, validated business document and its processing outcome, draft a professional, human-sounding email to the document's sender.

Tone:
- Warm but professional. You represent a competent small business, not a chatbot.
- Brief. Two to four short paragraphs. No corporate filler.
- Concrete. Reference specific values (amounts, invoice numbers, dates).

Three scenarios:
1. Clean confirmation — document parsed perfectly, no issues. Confirm receipt, state next step, thank.
2. Issue flagged — document has a fixable problem (missing tax ID, math mismatch, missing PO number). Acknowledge, specify exactly what's needed, offer a path forward.
3. High-risk escalation — document looks suspicious or unusually large. Acknowledge receipt; do NOT commit to action; flag that internal review is underway.

Output:
Return ONLY a single JSON object with two keys: "subject" and "body". The body should use \\n for line breaks. No markdown fences, no preamble."""


def _scenario_for(doc: ProcessedDocument) -> str:
    reasons = set(doc.actions.review_reasons)
    if ReviewReason.HIGH_VALUE in reasons or doc.risk_score >= 0.7:
        return "high_risk_escalation"
    if reasons - {ReviewReason.NONE}:
        return "issue_flagged"
    return "clean_confirmation"


def _build_context(doc: ProcessedDocument) -> str:
    return json.dumps(
        {
            "doc_type": doc.doc_type.value,
            "invoice_number": doc.invoice_number,
            "document_date": doc.document_date.isoformat() if doc.document_date else None,
            "due_date": doc.due_date.isoformat() if doc.due_date else None,
            "vendor_legal_name": doc.entity.legal_name,
            "vendor_email": doc.entity.email,
            "currency": doc.ledger.currency,
            "grand_total": str(doc.ledger.grand_total),
            "math_is_valid": doc.ledger.math_is_valid,
            "matched_vendor_id": doc.entity.matched_vendor_id,
            "risk_score": doc.risk_score,
            "review_reasons": [r.value for r in doc.actions.review_reasons],
            "scenario": _scenario_for(doc),
        },
        indent=2,
        default=str,
    )


async def draft_email(doc: ProcessedDocument) -> ProcessedDocument:
    if doc.entity.email is None and doc.entity.matched_vendor_id is None:
        log.info("comms_skipped_no_recipient")
        doc.actions.suggested_next_step = "Hold for AP review — no contact email on file."
        return doc

    user_message = (
        "Draft the appropriate email for this processed document:\n\n"
        f"```json\n{_build_context(doc)}\n```\n\n"
        "Return JSON only."
    )

    raw = await call_text(
        model=settings.communications_model,
        system=COMMUNICATIONS_SYSTEM,
        user_message=user_message,
        max_tokens=1024,
        effort="medium",
    )

    try:
        parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        doc.actions.draft_email_subject = parsed.get("subject")
        doc.actions.draft_email_body = parsed.get("body")
    except json.JSONDecodeError:
        log.warning("comms_json_parse_failed", raw_preview=raw[:200])
        doc.actions.draft_email_body = raw

    scenario = _scenario_for(doc)
    doc.actions.suggested_next_step = {
        "clean_confirmation": "Auto-post to ledger, send confirmation email.",
        "issue_flagged": "Send clarification email; pause posting until resolved.",
        "high_risk_escalation": "Escalate to bookkeeper review queue.",
    }[scenario]

    log.info("comms_drafted", scenario=scenario, has_subject=bool(doc.actions.draft_email_subject))
    return doc
