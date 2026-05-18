from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LeadStatus(str, Enum):
    DISCOVERED = "discovered"
    QUALIFIED = "qualified"
    REJECTED = "rejected"
    DRAFTED = "drafted"
    SUPPRESSED = "suppressed"


class DraftStatus(str, Enum):
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class ProspectingRun(Base):
    __tablename__ = "prospecting_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    geography: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, nullable=False)
    qualification_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_leads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    qualified_leads: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    drafts_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    leads: Mapped[list[Lead]] = relationship(back_populates="run", cascade="all, delete-orphan")
    email_drafts: Mapped[list[EmailDraft]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("prospecting_runs.id"), index=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    geography: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qualification_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    enrichment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run: Mapped[ProspectingRun] = relationship(back_populates="leads")
    email_drafts: Mapped[list[EmailDraft]] = relationship(
        back_populates="lead", cascade="all, delete-orphan"
    )


class EmailDraft(Base):
    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("prospecting_runs.id"), index=True, nullable=False
    )
    lead_id: Mapped[int] = mapped_column(ForeignKey("leads.id"), index=True, nullable=False)
    to_email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(160), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    send_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resend_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    run: Mapped[ProspectingRun] = relationship(back_populates="email_drafts")
    lead: Mapped[Lead] = relationship(back_populates="email_drafts")


class SuppressedRecipient(Base):
    __tablename__ = "suppressed_recipients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProspectingRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    niche: str = Field(min_length=3)
    geography: str = Field(min_length=2)
    max_results: int = Field(default=10, ge=1, le=50)
    qualification_threshold: float = Field(default=0.68, ge=0.0, le=1.0)


class ProspectingRunRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    trace_id: str
    niche: str
    geography: str
    max_results: int
    qualification_threshold: float
    status: RunStatus
    requested_at: datetime
    completed_at: datetime | None = None
    error: str | None = None
    created_leads: int = 0
    qualified_leads: int = 0
    drafts_created: int = 0


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: HttpUrl
    content: str = ""
    score: float = Field(default=0.0, ge=0.0)


class LeadProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    run_id: int | None = None
    company_name: str = Field(min_length=1)
    domain: str | None = None
    website_url: HttpUrl | None = None
    contact_email: EmailStr | None = None
    industry: str | None = None
    geography: str | None = None
    profile_summary: str = ""
    pain_points: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    revenue_indicators: list[str] = Field(default_factory=list)
    employee_indicators: list[str] = Field(default_factory=list)
    qualification_score: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    qualification_reason: str = ""
    status: LeadStatus = LeadStatus.DISCOVERED
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("domain")
    @classmethod
    def _normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.lower().strip().removeprefix("https://").removeprefix("http://")
        return cleaned.removeprefix("www.").split("/")[0] or None


class QualifiedLead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=1)
    domain: str | None = None
    website_url: HttpUrl | None = None
    contact_email: EmailStr | None = None
    industry: str | None = None
    geography: str | None = None
    profile_summary: str
    pain_points: list[str]
    revenue_indicators: list[str] = Field(default_factory=list)
    employee_indicators: list[str] = Field(default_factory=list)
    qualification_score: float = Field(ge=0.0, le=1.0)
    qualification_reason: str
    is_qualified: bool


class EmailDraftRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int | None = None
    run_id: int
    lead_id: int
    to_email: EmailStr
    subject: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1)
    body_html: str | None = None
    status: DraftStatus = DraftStatus.DRAFTED
    is_approved: bool = False
    approved_at: datetime | None = None
    approved_by: str | None = None
    created_at: datetime | None = None
    sent_at: datetime | None = None
    resend_message_id: str | None = None
    error: str | None = None
    send_attempts: int = 0


class DraftApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = Field(min_length=2, max_length=120)


class SendResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: int
    status: DraftStatus
    resend_message_id: str | None = None
    error: str | None = None
    sent_at: datetime | None = None
