from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from rapidfuzz import fuzz, process

from ..config import settings
from ..logging_setup import get_logger
from ..models.schemas import ProcessedDocument, ReviewReason

log = get_logger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

with open(_DATA_DIR / "vendors.json") as f:
    VENDORS: list[dict] = json.load(f)

with open(_DATA_DIR / "chart_of_accounts.json") as f:
    CHART_OF_ACCOUNTS: dict[str, dict] = json.load(f)

_VENDOR_LOOKUP: list[tuple[str, dict]] = []
for v in VENDORS:
    for name in [v["legal_name"], *v.get("aliases", [])]:
        _VENDOR_LOOKUP.append((name, v))


def _match_vendor(legal_name: str) -> tuple[dict | None, float]:
    if not legal_name:
        return None, 0.0
    choices = [name for name, _ in _VENDOR_LOOKUP]
    match = process.extractOne(legal_name, choices, scorer=fuzz.WRatio)
    if match is None:
        return None, 0.0
    matched_name, score, idx = match
    if score < settings.fuzzy_match_threshold:
        return None, score / 100.0
    return _VENDOR_LOOKUP[idx][1], score / 100.0


def _classify_line_item(description: str, vendor_preferred: str | None) -> str:
    desc_lower = description.lower()
    if vendor_preferred and vendor_preferred in CHART_OF_ACCOUNTS:
        return vendor_preferred

    for account_code, account in CHART_OF_ACCOUNTS.items():
        if account_code == "9999":
            continue
        for kw in account["keywords"]:
            if kw in desc_lower:
                return account_code
    return "9999"


def _compute_risk_score(doc: ProcessedDocument) -> tuple[float, list[ReviewReason]]:
    reasons: list[ReviewReason] = []
    risk = 0.0

    if not doc.ledger.math_is_valid:
        reasons.append(ReviewReason.MATH_MISMATCH)
        risk += 0.4

    if doc.entity.tax_id is None and doc.doc_type.value in {"invoice", "w9"}:
        reasons.append(ReviewReason.MISSING_TAX_ID)
        risk += 0.25

    if doc.entity.matched_vendor_id is None:
        reasons.append(ReviewReason.UNKNOWN_VENDOR)
        risk += 0.2

    if doc.document_date and doc.due_date and doc.due_date < doc.document_date:
        reasons.append(ReviewReason.DATE_INCONSISTENCY)
        risk += 0.3

    if doc.ledger.grand_total > Decimal("5000"):
        reasons.append(ReviewReason.HIGH_VALUE)
        risk += 0.15

    return min(risk, 1.0), reasons


def enrich(doc: ProcessedDocument) -> ProcessedDocument:
    vendor, confidence = _match_vendor(doc.entity.legal_name)
    doc.entity.match_confidence = confidence
    if vendor is not None:
        doc.entity.matched_vendor_id = vendor["id"]
        if not doc.entity.tax_id:
            doc.entity.tax_id = vendor.get("tax_id")

    preferred = vendor.get("preferred_account") if vendor else None
    for item in doc.ledger.line_items:
        item.ledger_account = _classify_line_item(item.description, preferred)

    risk, reasons = _compute_risk_score(doc)
    doc.risk_score = risk
    doc.actions.review_reasons = reasons
    doc.actions.requires_human_review = risk >= 0.5 or any(
        r in {ReviewReason.MATH_MISMATCH, ReviewReason.DATE_INCONSISTENCY}
        for r in reasons
    )

    log.info(
        "intelligence_enrich",
        vendor_id=doc.entity.matched_vendor_id,
        match_confidence=confidence,
        risk_score=risk,
        needs_review=doc.actions.requires_human_review,
        reasons=[r.value for r in reasons],
    )
    return doc
