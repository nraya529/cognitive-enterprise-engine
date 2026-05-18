from __future__ import annotations

from anthropic.types import ToolParam

from ..config import settings
from ..logging_setup import get_logger
from ..services.anthropic_client import call_with_tools, extract_tool_use

log = get_logger(__name__)


EXTRACTION_TOOL: ToolParam = {
    "name": "submit_extracted_document",
    "description": (
        "Submit the fully extracted business document as a strictly structured payload. "
        "All monetary values must be numeric (no currency symbols, no thousands separators). "
        "All dates must be ISO 8601 (YYYY-MM-DD). Quantities default to 1 when absent."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "doc_type": {
                "type": "string",
                "enum": [
                    "invoice", "receipt", "purchase_order", "w9",
                    "hr_onboarding", "expense_report", "unknown",
                ],
            },
            "document_date": {"type": ["string", "null"], "description": "ISO 8601 date"},
            "due_date": {"type": ["string", "null"], "description": "ISO 8601 date"},
            "invoice_number": {"type": ["string", "null"]},
            "entity": {
                "type": "object",
                "properties": {
                    "legal_name": {"type": "string"},
                    "tax_id": {"type": ["string", "null"], "description": "EIN or SSN, 9-10 digits"},
                    "email": {"type": ["string", "null"]},
                    "phone": {"type": ["string", "null"]},
                    "address": {"type": ["string", "null"]},
                },
                "required": ["legal_name"],
            },
            "ledger": {
                "type": "object",
                "properties": {
                    "currency": {"type": "string", "default": "USD"},
                    "line_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "quantity": {"type": "number", "minimum": 0},
                                "unit_price": {"type": "number", "minimum": 0},
                                "total": {"type": "number", "minimum": 0},
                            },
                            "required": ["description", "quantity", "unit_price", "total"],
                        },
                    },
                    "subtotal": {"type": "number", "minimum": 0},
                    "tax_amount": {"type": "number", "minimum": 0, "default": 0},
                    "grand_total": {"type": "number", "minimum": 0},
                },
                "required": ["subtotal", "grand_total"],
            },
        },
        "required": ["doc_type", "entity", "ledger"],
    },
}


EXTRACTION_SYSTEM = """You are the Cognitive Extraction Agent for an autonomous back-office system.

Your function: ingest raw, chaotic, unstructured business document text and emit a strictly typed structured payload via the `submit_extracted_document` tool.

Rules:
1. Normalize every monetary value to a plain number. No "$", no commas, no currency suffixes inside numbers.
2. Convert every date to ISO 8601 (YYYY-MM-DD). If the year is missing, infer from context (received date, due date proximity).
3. Tax IDs (EIN/SSN) must be returned as digit strings, optionally with the standard hyphen (XX-XXXXXXX).
4. If a field is genuinely absent, return null rather than fabricating.
5. Every line item must satisfy: quantity * unit_price == total (within $0.02 rounding).
6. The grand_total must equal subtotal + tax_amount (within $0.02).
7. If the document is so degraded you cannot extract reliably, set doc_type="unknown" and populate whatever you can.

You must ALWAYS call `submit_extracted_document` exactly once. Never reply with plain text."""


CORRECTION_SYSTEM_SUFFIX = """

A previous extraction attempt failed validation. The errors are listed below. Re-extract the document carefully, correcting each error. Pay particular attention to arithmetic consistency."""


async def extract(raw_text: str, errors: list[dict] | None = None) -> dict:
    system = EXTRACTION_SYSTEM
    user_content = f"<document>\n{raw_text}\n</document>\n\nExtract this document now."

    if errors:
        system = EXTRACTION_SYSTEM + CORRECTION_SYSTEM_SUFFIX
        error_block = "\n".join(f"- {e['field_path']}: {e['error']}" for e in errors)
        user_content = (
            f"<document>\n{raw_text}\n</document>\n\n"
            f"<previous_errors>\n{error_block}\n</previous_errors>\n\n"
            "Re-extract, correcting the errors above."
        )

    response = await call_with_tools(
        model=settings.extraction_model,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "submit_extracted_document"},
        max_tokens=8192,
        effort="high",
    )

    payload = extract_tool_use(response, "submit_extracted_document")
    if payload is None:
        raise RuntimeError("Extraction agent did not invoke the submit tool")
    log.info("extraction_complete", doc_type=payload.get("doc_type"), corrected=bool(errors))
    return payload
