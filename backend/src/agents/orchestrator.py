from __future__ import annotations

from ..logging_setup import get_logger, new_trace_id
from ..models.schemas import ProcessedDocument
from . import communications, intelligence, verification

log = get_logger(__name__)


async def process_document(raw_text: str) -> ProcessedDocument:
    trace_id = new_trace_id()
    log.info("pipeline_start", chars=len(raw_text))

    doc, warnings = await verification.verify_and_heal(raw_text, trace_id)
    log.info("stage_verify_done", warnings=len(warnings))

    doc = intelligence.enrich(doc)
    log.info("stage_intel_done", risk=doc.risk_score)

    doc = await communications.draft_email(doc)
    log.info("pipeline_complete", needs_review=doc.actions.requires_human_review)
    return doc
