from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from ..config import settings
from ..logging_setup import get_logger
from ..models.schemas import (
    AutonomousActions,
    EntityProfile,
    FinancialLedger,
    LineItem,
    ProcessedDocument,
    VerificationError,
)
from . import extraction

log = get_logger(__name__)


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except InvalidOperation as e:
        raise ValueError(f"not numeric: {v!r}") from e


def _hydrate(payload: dict, trace_id: str, raw_excerpt: str) -> ProcessedDocument:
    entity = EntityProfile(**payload["entity"])

    ledger_in = payload["ledger"]
    line_items = [
        LineItem(
            description=li["description"],
            quantity=_to_decimal(li["quantity"]),
            unit_price=_to_decimal(li["unit_price"]),
            total=_to_decimal(li["total"]),
        )
        for li in ledger_in.get("line_items", [])
    ]
    ledger = FinancialLedger(
        currency=ledger_in.get("currency", "USD"),
        line_items=line_items,
        subtotal=_to_decimal(ledger_in["subtotal"]),
        tax_amount=_to_decimal(ledger_in.get("tax_amount", 0)),
        grand_total=_to_decimal(ledger_in["grand_total"]),
    )

    return ProcessedDocument(
        trace_id=trace_id,
        doc_type=payload["doc_type"],
        document_date=payload.get("document_date"),
        due_date=payload.get("due_date"),
        invoice_number=payload.get("invoice_number"),
        entity=entity,
        ledger=ledger,
        actions=AutonomousActions(),
        raw_excerpt=raw_excerpt[:500],
    )


def _format_validation_errors(exc: ValidationError) -> list[VerificationError]:
    errs: list[VerificationError] = []
    for err in exc.errors():
        path = ".".join(str(p) for p in err["loc"])
        errs.append(
            VerificationError(
                field_path=path, error=err["msg"], severity="fatal"
            )
        )
    return errs


async def verify_and_heal(
    raw_text: str, trace_id: str
) -> tuple[ProcessedDocument, list[VerificationError]]:
    """Extract, validate, and recursively self-heal on failure.

    Returns the final document plus any non-fatal warnings. Raises if even after
    `max_self_heal_attempts` the extraction still fails fatal validation.
    """
    errors_to_correct: list[dict] = []
    last_validation_errors: list[VerificationError] = []

    for attempt in range(settings.max_self_heal_attempts + 1):
        payload = await extraction.extract(
            raw_text, errors=errors_to_correct if errors_to_correct else None
        )
        try:
            doc = _hydrate(payload, trace_id, raw_text)
            doc.self_heal_attempts = attempt
            warnings: list[VerificationError] = []
            if not doc.ledger.math_is_valid:
                warnings.append(
                    VerificationError(
                        field_path="ledger.grand_total",
                        error="subtotal + tax does not equal grand_total",
                        severity="warning",
                    )
                )
            log.info(
                "verification_success",
                attempt=attempt,
                doc_type=doc.doc_type.value,
                math_valid=doc.ledger.math_is_valid,
            )
            return doc, warnings
        except (ValidationError, ValueError) as e:
            if isinstance(e, ValidationError):
                last_validation_errors = _format_validation_errors(e)
            else:
                last_validation_errors = [
                    VerificationError(
                        field_path="<root>", error=str(e), severity="fatal"
                    )
                ]
            errors_to_correct = [
                {"field_path": err.field_path, "error": err.error}
                for err in last_validation_errors
            ]
            log.warning(
                "verification_failed",
                attempt=attempt,
                errors=[(e.field_path, e.error) for e in last_validation_errors],
            )

    raise RuntimeError(
        f"Self-healing exhausted after {settings.max_self_heal_attempts + 1} attempts: "
        f"{[(e.field_path, e.error) for e in last_validation_errors]}"
    )
