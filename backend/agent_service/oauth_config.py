"""Google OAuth configuration — shared by our consent flow and token minting.

Env name mapping: our ``.env`` carries ``OAUTH_GOOGLE_CLIENT_ID/SECRET`` (also
accepted: ``GOOGLE_OAUTH_CLIENT_ID/SECRET``, the name workspace-mcp uses). The
same client credentials feed both our consent flow and access-token refresh.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URI = "https://www.googleapis.com/oauth2/v3/userinfo"

# Scopes must match what workspace-mcp needs for search/fetch/send/label.
GOOGLE_SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        val = os.getenv(name)
        if val:
            return val
    return default


@dataclass(frozen=True)
class OAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str

    @classmethod
    def from_env(cls) -> "OAuthConfig":
        return cls(
            client_id=_first_env("OAUTH_GOOGLE_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID"),
            client_secret=_first_env(
                "OAUTH_GOOGLE_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET"
            ),
            redirect_uri=os.getenv(
                "OAUTH_REDIRECT_URI",
                "http://localhost:8001/oauth/google/callback",
            ),
        )
