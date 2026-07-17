"""Pydantic models for agent context and structured outputs."""

from __future__ import annotations

from pydantic import BaseModel


class IncomingEmail(BaseModel):
    """The email the pipeline drafts a reply to."""

    message_id: str
    thread_id: str | None = None
    from_addr: str | None = None
    subject: str | None = None
    body: str = ""


class StructuredReply(BaseModel):
    """Structure agent output — the concrete reply to send."""

    subject: str
    body: str
    in_reply_to: str | None = None


class RevisionContext(BaseModel):
    """Local context for the Reviewer agent — nothing is persisted."""

    original_email: str
    rejected_draft: str
    user_feedback: str


class SummaryOutput(BaseModel):
    """Summarizer output for the Done/ audit sidecar."""

    summary: str
    status: str = "completed"
