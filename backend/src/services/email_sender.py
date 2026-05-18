from __future__ import annotations

import asyncio
from datetime import datetime, time, timezone

import httpx

from ..config import settings
from ..logging_setup import get_logger
from ..models.leads import DraftStatus, EmailDraftRead, SendResult
from . import storage

log = get_logger(__name__)


class TransientSendError(RuntimeError):
    """Raised when a Resend call fails for a reason that's worth retrying."""


def _email_domain(email: str) -> str:
    return email.rsplit("@", 1)[-1].lower()


async def _post_to_resend(payload: dict, idempotency_key: str) -> str | None:
    headers = {
        "Authorization": f"Bearer {settings.resend_api_key}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key,
    }
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(base_url=settings.resend_base_url, timeout=timeout) as client:
        response = await client.post("/emails", json=payload, headers=headers)
    if response.status_code == 429:
        retry_after = float(response.headers.get("retry-after", "1"))
        raise TransientSendError(f"resend rate limited; retry-after={retry_after}s")
    if response.status_code >= 500:
        raise TransientSendError(f"resend {response.status_code}: {response.text[:200]}")
    response.raise_for_status()
    return response.json().get("id")


async def _send_with_retry(payload: dict, idempotency_key: str, max_attempts: int = 3) -> str | None:
    delay = 1.0
    for attempt in range(1, max_attempts + 1):
        try:
            return await _post_to_resend(payload, idempotency_key)
        except TransientSendError as exc:
            if attempt == max_attempts:
                raise
            log.warning("resend_retry", attempt=attempt, reason=str(exc))
            await asyncio.sleep(delay)
            delay *= 2
    return None


async def send_approved_draft(draft: EmailDraftRead) -> SendResult:
    if draft.id is None:
        raise ValueError("draft must be persisted before sending")
    if draft.status == DraftStatus.SENT:
        return SendResult(
            draft_id=draft.id,
            status=DraftStatus.SENT,
            resend_message_id=draft.resend_message_id,
            sent_at=draft.sent_at,
        )
    if not draft.is_approved or draft.status != DraftStatus.APPROVED or draft.approved_at is None:
        raise PermissionError("draft must be approved before sending")
    if _email_domain(str(draft.to_email)) in settings.blocked_domain_set:
        raise PermissionError("recipient domain is blocked")
    if await storage.is_email_suppressed(str(draft.to_email)):
        raise PermissionError("recipient is suppressed or already received an email")
    if not settings.resend_api_key:
        raise RuntimeError("RESEND_API_KEY is required to send drafts")

    if await storage.sent_count_for_run(draft.run_id) >= settings.outbound_run_send_limit:
        raise PermissionError("run send limit reached")

    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    if await storage.sent_count_since(today_start) >= settings.outbound_daily_send_limit:
        raise PermissionError("daily send limit reached")

    payload: dict = {
        "from": settings.outbound_from_email,
        "to": [str(draft.to_email)],
        "subject": draft.subject,
        "text": draft.body,
    }
    if draft.body_html:
        payload["html"] = draft.body_html
    if settings.outbound_reply_to_email:
        payload["reply_to"] = [settings.outbound_reply_to_email]

    idempotency_key = f"draft-{draft.id}-{draft.send_attempts}"
    resend_message_id = await _send_with_retry(payload, idempotency_key)

    sent = await storage.mark_draft_sent(draft.id, resend_message_id)
    log.info("outbound_email_sent", draft_id=draft.id, resend_message_id=sent.resend_message_id)
    return SendResult(
        draft_id=draft.id,
        status=sent.status,
        resend_message_id=sent.resend_message_id,
        sent_at=sent.sent_at,
    )
