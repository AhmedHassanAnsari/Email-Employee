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

from db.repository import get_email, list_by_user, set_status
from db.session import SessionDep
from .. import agent as pipeline
from ..auth_client import AuthClient
from ..gmail_mcp import gmail_server_for_token
from ..models import IncomingEmail, StructuredReply
from ..notify import NotificationEvent, notify
from ..storage import approval_payload_path, done_summary_path

router = APIRouter(prefix="/emails", tags=["lifecycle"])

# DB status -> the UI folder it belongs in.
_FOLDER_FOR_STATUS = {
    "pending": "inbox",
    "drafted": "approval",
    "approved": "approval",
    "sent": "done",
    "failed": "inbox",
}


class RejectBody(BaseModel):
    feedback: str


def _read_json(path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _serialize(email) -> dict:
    """Shape a DB row (+ its on-disk artefact) into the UI's event model."""
    folder = _FOLDER_FOR_STATUS.get(email.status, "inbox")
    description = email.snippet or ""
    final_response = None
    summary = None

    if folder == "approval":
        draft = _read_json(approval_payload_path(email.id))
        description = draft.get("body") or email.draft_response or description
    elif folder == "done":
        done = _read_json(done_summary_path(email.id))
        final_response = done.get("final_response") or email.draft_response
        summary = done.get("summary")
        description = summary or final_response or description

    return {
        "id": str(email.id),
        "status": folder,
        "title": email.subject or "(no subject)",
        "from": email.from_addr,
        "description": description,
        "snippet": email.snippet or "",
        "draft_response": email.draft_response,
        "final_response": final_response,
        "summary": summary,
        "db_status": email.status,
    }


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


@router.get("")
async def list_emails(session: SessionDep, user_id: str) -> dict:
    """All of a user's emails, bucketed into inbox / approval / done for the UI."""
    rows = await list_by_user(session, user_id)
    buckets: dict[str, list[dict]] = {"inbox": [], "approval": [], "done": []}
    for row in rows:
        event = _serialize(row)
        buckets[event["status"]].append(event)
    return buckets


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
