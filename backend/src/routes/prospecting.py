from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from ..agents.prospecting.orchestrator import run_prospecting
from ..config import settings
from ..logging_setup import get_logger, new_trace_id
from ..models.leads import (
    DraftApprovalRequest,
    DraftStatus,
    EmailDraftRead,
    LeadProfile,
    LeadStatus,
    ProspectingRunRead,
    ProspectingRunRequest,
    SendResult,
)
from ..services import email_sender, storage

router = APIRouter(prefix="/prospecting", tags=["prospecting"])
log = get_logger(__name__)


def _default_run_request() -> ProspectingRunRequest:
    return ProspectingRunRequest(
        niche=settings.default_prospecting_niche,
        geography=settings.default_prospecting_geography,
        max_results=settings.default_prospecting_max_results,
        qualification_threshold=settings.minimum_qualification_score,
    )


@router.post("/runs", response_model=ProspectingRunRead, status_code=status.HTTP_202_ACCEPTED)
async def create_prospecting_run(
    background_tasks: BackgroundTasks,
    request: ProspectingRunRequest | None = None,
) -> ProspectingRunRead:
    trace_id = new_trace_id()
    run = await storage.create_run(request or _default_run_request(), trace_id=trace_id)
    background_tasks.add_task(run_prospecting, run.id)
    log.info("prospecting_run_queued", run_id=run.id)
    return run


@router.post("/runs/{run_id}/execute", response_model=ProspectingRunRead)
async def execute_prospecting_run(run_id: int) -> ProspectingRunRead:
    try:
        return await run_prospecting(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/runs", response_model=list[ProspectingRunRead])
async def list_prospecting_runs(
    limit: int = Query(default=25, ge=1, le=100),
) -> list[ProspectingRunRead]:
    return await storage.list_runs(limit=limit)


@router.get("/runs/{run_id}", response_model=ProspectingRunRead)
async def get_prospecting_run(run_id: int) -> ProspectingRunRead:
    try:
        return await storage.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/leads", response_model=list[LeadProfile])
async def list_leads(
    run_id: int | None = None,
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
) -> list[LeadProfile]:
    return await storage.list_leads(run_id=run_id, status=status_filter)


@router.get("/drafts", response_model=list[EmailDraftRead])
async def list_drafts(
    run_id: int | None = None,
    status_filter: DraftStatus | None = Query(default=None, alias="status"),
) -> list[EmailDraftRead]:
    return await storage.list_drafts(run_id=run_id, status=status_filter)


@router.post("/drafts/{draft_id}/approve", response_model=EmailDraftRead)
async def approve_draft(draft_id: int, request: DraftApprovalRequest) -> EmailDraftRead:
    try:
        draft = await storage.approve_draft(draft_id, request.approved_by)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    log.info("outbound_draft_approved", draft_id=draft.id, approved_by=request.approved_by)
    return draft


@router.post("/drafts/{draft_id}/send", response_model=SendResult)
async def send_draft(draft_id: int) -> SendResult:
    try:
        draft = await storage.get_draft(draft_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        return await email_sender.send_approved_draft(draft)
    except PermissionError as exc:
        # 409 = the draft is in a state that disallows sending (not approved,
        # blocked domain, rate limit). The draft is NOT marked failed — the
        # operator can fix the gate and try again.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        # Misconfiguration (missing API key). Treat as 503, do not mutate state.
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        # Genuine delivery failure: persist the error and surface as 502.
        await storage.mark_draft_failed(draft_id, str(exc))
        log.exception("send_draft_failed", draft_id=draft_id)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
