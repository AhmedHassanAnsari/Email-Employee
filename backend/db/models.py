"""SQLModel schema — two app-owned tables.

* ``emails`` — the per-email state machine the poller dedups against and the
  lifecycle endpoints transition.
* ``google_tokens`` — per-user Google refresh token (encrypted). WE own the
  OAuth flow in external-provider mode; Python mints fresh access tokens from
  the stored refresh token per task and passes them to workspace-mcp.

NOTE: no ``from __future__ import annotations`` — SQLAlchemy 2.0's relationship
resolver needs real string forward-refs, not stringized annotations.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# Workflow states: fetched -> drafted -> approved -> sent (or failed).
EMAIL_STATUSES = ("pending", "drafted", "approved", "sent", "failed")


class Email(SQLModel, table=True):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("gmail_message_id", name="uq_emails_gmail_message_id"),
        CheckConstraint(
            "status IN ('pending','drafted','approved','sent','failed')",
            name="ck_emails_status",
        ),
        Index("idx_emails_user_status", "user_id", "status"),
    )

    id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    user_id: str = Field(sa_column=Column(Text, nullable=False))
    gmail_message_id: str = Field(sa_column=Column(Text, nullable=False))
    gmail_thread_id: Optional[str] = Field(default=None, sa_column=Column(Text))

    from_addr: Optional[str] = Field(default=None, sa_column=Column(Text))
    subject: Optional[str] = Field(default=None, sa_column=Column(Text))
    snippet: Optional[str] = Field(default=None, sa_column=Column(Text))

    status: str = Field(
        default="pending",
        sa_column=Column(Text, nullable=False, server_default=text("'pending'")),
    )
    draft_response: Optional[str] = Field(default=None, sa_column=Column(Text))
    metadata_json: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=text("now()"), nullable=False
        ),
    )


class GoogleToken(SQLModel, table=True):
    """Per-user Google OAuth refresh token, encrypted at rest (Fernet).

    ``user_id`` is the user's Google email (workspace-mcp routes by the email in
    the minted access token, so we key on it directly). One row per authorized
    inbox; the poller's user list is ``SELECT user_id FROM google_tokens``.
    """

    __tablename__ = "google_tokens"

    user_id: str = Field(sa_column=Column(Text, primary_key=True))
    refresh_token_enc: str = Field(sa_column=Column(Text, nullable=False))
    scopes: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=text("now()"), nullable=False
        ),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("now()"),
            onupdate=text("now()"),
            nullable=False,
        ),
    )
