"""Email lifecycle routes.

* POST /emails/{id}/solve   — Writer->Structure pipeline; write approval artefact;
                              set 'drafted'; notify (approval).
* POST /emails/{id}/approve — send reply in-thread via Gmail MCP; write Done
                              summary; set 'sent'; notify (done).
* POST /emails/{id}/reject  — refine draft from feedback (in-memory); rewrite
                              approval artefact; back to 'drafted'.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db.repository import get_email, set_status
from db.session import SessionDep
from .. import agent as pipeline
from ..auth_client import AuthClient
from ..gmail_mcp import gmail_server_for_token
from ..models import IncomingEmail, StructuredReply
from ..notify import NotificationEvent, notify
from ..storage import approval_payload_path, done_summary_path

router = APIRouter(prefix="/emails", tags=["lifecycle"])


class RejectBody(BaseModel):
    feedback: str


def _incoming_from_row(email) -> IncomingEmail:
    return IncomingEmail(
        message_id=email.gmail_message_id,
        thread_id=email.gmail_thread_id,
        from_addr=email.from_addr,
        subject=email.subject,
        body=email.snippet or "",
    )


def _write_approval(email_id: int, reply: StructuredReply) -> None:
    approval_payload_path(email_id).write_text(
        json.dumps(reply.model_dump(), indent=2), encoding="utf-8"
    )


async def _load(session, email_id: int):
    email = await get_email(session, email_id)
    if email is None:
        raise HTTPException(status_code=404, detail="email not found")
    return email


@router.post("/{email_id}/solve")
async def solve(email_id: int, session: SessionDep) -> dict:
    email = await _load(session, email_id)
    auth = AuthClient()
    token = await auth.get_access_token(email.user_id)

    async with gmail_server_for_token(token) as gmail:
        reply = await pipeline.draft_reply(_incoming_from_row(email), gmail)

    _write_approval(email_id, reply)
    await set_status(session, email, "drafted", draft_response=reply.body)
    await notify(
        NotificationEvent(event_type="approval", email_id=email_id, subject=reply.subject)
    )
    return {"email_id": email_id, "status": "drafted", "subject": reply.subject}


@router.post("/{email_id}/approve")
async def approve(email_id: int, session: SessionDep) -> dict:
    email = await _load(session, email_id)
    if not email.draft_response:
        raise HTTPException(status_code=409, detail="no draft to approve")

    auth = AuthClient()
    token = await auth.get_access_token(email.user_id)

    subject = email.subject or "(no subject)"
    async with gmail_server_for_token(token) as gmail:
        await gmail.call_tool(
            "send_gmail_message",
            {
                "to": email.from_addr,
                "subject": subject,
                "body": email.draft_response,
                "thread_id": email.gmail_thread_id,
            },
        )
        summary = await pipeline.summarize(email.snippet or "", email.draft_response)

    await set_status(session, email, "sent")
    done_summary_path(email_id).write_text(
        json.dumps(
            {
                "email_id": email_id,
                "subject": subject,
                "from": email.from_addr,
                "final_response": email.draft_response,
                "summary": summary.summary,
                "status": "sent",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    # The email has moved to Done/; drop its pending-approval artefact.
    approval_payload_path(email_id).unlink(missing_ok=True)
    await notify(
        NotificationEvent(
            event_type="done", email_id=email_id, subject=subject, summary=summary.summary
        )
    )
    return {"email_id": email_id, "status": "sent"}


@router.post("/{email_id}/reject")
async def reject(email_id: int, body: RejectBody, session: SessionDep) -> dict:
    email = await _load(session, email_id)
    if not email.draft_response:
        raise HTTPException(status_code=409, detail="no draft to reject")

    revised = await pipeline.revise_reply(
        original_email=email.snippet or "",
        rejected_draft=email.draft_response,
        user_feedback=body.feedback,
    )
    reply = StructuredReply(
        subject=email.subject or "(no subject)",
        body=revised,
        in_reply_to=email.gmail_thread_id,
    )
    _write_approval(email_id, reply)
    await set_status(session, email, "drafted", draft_response=revised)
    await notify(
        NotificationEvent(event_type="approval", email_id=email_id, subject=reply.subject)
    )
    return {"email_id": email_id, "status": "drafted", "revised": True}
