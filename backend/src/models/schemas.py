from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DocType(str, Enum):
    INVOICE = "invoice"
    RECEIPT = "receipt"
    PURCHASE_ORDER = "purchase_order"
    W9 = "w9"
    HR_ONBOARDING = "hr_onboarding"
    EXPENSE_REPORT = "expense_report"
    UNKNOWN = "unknown"


class ReviewReason(str, Enum):
    MATH_MISMATCH = "math_mismatch"
    MISSING_TAX_ID = "missing_tax_id"
    DATE_INCONSISTENCY = "date_inconsistency"
    UNKNOWN_VENDOR = "unknown_vendor"
    HIGH_VALUE = "high_value"
    DUPLICATE_SUSPECTED = "duplicate_suspected"
    PARSE_FAILURE = "parse_failure"
    NONE = "none"


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    total: Decimal = Field(ge=0)
    ledger_account: str | None = None

    @model_validator(mode="after")
    def _check_total(self) -> "LineItem":
        expected = (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        actual = self.total.quantize(Decimal("0.01"))
        if abs(expected - actual) > Decimal("0.02"):
            raise ValueError(
                f"line item total {actual} != quantity*unit_price {expected} "
                f"(desc={self.description!r})"
            )
        return self


class EntityProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_name: str = Field(min_length=1)
    tax_id: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    matched_vendor_id: str | None = None
    match_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("tax_id")
    @classmethod
    def _check_tax_id(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = "".join(c for c in v if c.isdigit())
        if len(digits) not in (9, 10):
            raise ValueError(f"tax_id must contain 9-10 digits, got {len(digits)}")
        return v


class FinancialLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(default="USD", min_length=3, max_length=3)
    line_items: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    grand_total: Decimal = Field(ge=0)
    math_is_valid: bool = False

    @model_validator(mode="after")
    def _validate_math(self) -> "FinancialLedger":
        if self.line_items:
            items_sum = sum((li.total for li in self.line_items), start=Decimal("0"))
            if abs(items_sum - self.subtotal) > Decimal("0.02"):
                self.math_is_valid = False
                return self
        expected_total = (self.subtotal + self.tax_amount).quantize(Decimal("0.01"))
        actual_total = self.grand_total.quantize(Decimal("0.01"))
        self.math_is_valid = abs(expected_total - actual_total) <= Decimal("0.02")
        return self


class AutonomousActions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requires_human_review: bool = False
    review_reasons: list[ReviewReason] = Field(default_factory=list)
    suggested_next_step: str = ""
    draft_email_subject: str | None = None
    draft_email_body: str | None = None


class ProcessedDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: str
    doc_type: DocType
    document_date: date | None = None
    due_date: date | None = None
    invoice_number: str | None = None
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp_processed: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    entity: EntityProfile
    ledger: FinancialLedger
    actions: AutonomousActions

    self_heal_attempts: int = 0
    raw_excerpt: str = ""

    @model_validator(mode="after")
    def _check_dates(self) -> "ProcessedDocument":
        if self.document_date and self.due_date and self.due_date < self.document_date:
            raise ValueError(
                f"due_date {self.due_date} cannot precede document_date {self.document_date}"
            )
        return self


class WebhookPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: Literal["email", "upload", "make_com", "zapier", "test"] = "email"
    raw_text: str = Field(default="", description="Raw unstructured document text")
    sender_email: str | None = None
    received_at: datetime | None = None
    attachments: list[str] = Field(default_factory=list)


class VerificationError(BaseModel):
    field_path: str
    error: str
    severity: Literal["fatal", "warning"] = "warning"
