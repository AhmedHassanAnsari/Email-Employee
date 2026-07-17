"""Google access-token minting (external-provider mode).

WE own the OAuth flow: each user's Google **refresh token** lives encrypted in
``google_tokens``. Per task we mint a fresh ``ya29.*`` access token from it and
pass that to workspace-mcp as a per-request bearer. This replaces the dropped
Better Auth ``/internal/token`` client.

* ``list_users()``          -> user ids (Google emails) with authorized inboxes
* ``get_access_token(uid)``  -> fresh Google access token for that user
"""

from __future__ import annotations

import httpx

from db.repository import get_google_token, list_token_user_ids
from db.session import module_sessionmaker

from .crypto import decrypt
from .oauth_config import GOOGLE_TOKEN_URI, OAuthConfig


class AuthServiceError(RuntimeError):
    pass


class AuthClient:
    """Mints Google access tokens from stored per-user refresh tokens."""

    def __init__(self, config: OAuthConfig | None = None) -> None:
        self.config = config or OAuthConfig.from_env()

    async def list_users(self) -> list[str]:
        """User ids (Google emails) that have authorized inbox access."""
        sm = module_sessionmaker()
        async with sm() as session:
            return await list_token_user_ids(session)

    async def get_access_token(self, user_id: str) -> str:
        """Fresh Google access token for ``user_id`` (minted from refresh token)."""
        sm = module_sessionmaker()
        async with sm() as session:
            row = await get_google_token(session, user_id)
        if row is None:
            raise AuthServiceError(f"no Google token stored for user {user_id!r}")

        refresh_token = decrypt(row.refresh_token_enc)
        data = {
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URI, data=data)
        if resp.status_code >= 400:
            raise AuthServiceError(
                f"token refresh for {user_id} failed: HTTP {resp.status_code} {resp.text}"
            )
        token = resp.json().get("access_token")
        if not token:
            raise AuthServiceError(
                f"token refresh for {user_id}: no access_token in response"
            )
        return token
