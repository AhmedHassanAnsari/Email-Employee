"""Data-access helpers for the ``emails`` table."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Email, GoogleToken


async def get_email(session: AsyncSession, email_id: int) -> Optional[Email]:
    return await session.get(Email, email_id)


async def get_by_message_id(
    session: AsyncSession, gmail_message_id: str
) -> Optional[Email]:
    result = await session.execute(
        select(Email).where(Email.gmail_message_id == gmail_message_id)
    )
    return result.scalar_one_or_none()


async def list_processed_message_ids(session: AsyncSession) -> set[str]:
    """All Gmail message ids we've already ingested — the restart-safe dedup guard."""
    result = await session.execute(select(Email.gmail_message_id))
    return set(result.scalars().all())


async def upsert_incoming(
    session: AsyncSession,
    *,
    user_id: str,
    gmail_message_id: str,
    gmail_thread_id: str | None,
    from_addr: str | None,
    subject: str | None,
    snippet: str | None,
) -> Email:
    """Insert a newly detected email as ``pending`` (idempotent on message id)."""
    existing = await get_by_message_id(session, gmail_message_id)
    if existing is not None:
        return existing
    email = Email(
        user_id=user_id,
        gmail_message_id=gmail_message_id,
        gmail_thread_id=gmail_thread_id,
        from_addr=from_addr,
        subject=subject,
        snippet=snippet,
        status="pending",
    )
    session.add(email)
    await session.commit()
    return email


async def set_status(
    session: AsyncSession,
    email: Email,
    status: str,
    *,
    draft_response: str | None = None,
) -> Email:
    email.status = status
    if draft_response is not None:
        email.draft_response = draft_response
    session.add(email)
    await session.commit()
    return email


# --- google_tokens ---------------------------------------------------------


async def get_google_token(
    session: AsyncSession, user_id: str
) -> Optional[GoogleToken]:
    return await session.get(GoogleToken, user_id)


async def list_token_user_ids(session: AsyncSession) -> list[str]:
    """All users who have authorized inbox access — the poller's outer loop."""
    result = await session.execute(select(GoogleToken.user_id))
    return list(result.scalars().all())


async def upsert_google_token(
    session: AsyncSession,
    *,
    user_id: str,
    refresh_token_enc: str,
    scopes: str | None,
) -> GoogleToken:
    """Store (or replace) a user's encrypted refresh token.

    Only overwrites the refresh token when a new one is provided — Google omits
    it on re-consent unless ``prompt=consent`` was used, so callers should pass
    ``None`` for ``refresh_token_enc`` when they want to keep the existing one.
    """
    existing = await get_google_token(session, user_id)
    if existing is not None:
        if refresh_token_enc:
            existing.refresh_token_enc = refresh_token_enc
        if scopes is not None:
            existing.scopes = scopes
        session.add(existing)
        await session.commit()
        return existing
    token = GoogleToken(
        user_id=user_id,
        refresh_token_enc=refresh_token_enc,
        scopes=scopes,
    )
    session.add(token)
    await session.commit()
    return token
