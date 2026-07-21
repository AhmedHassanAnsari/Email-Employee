"""Our Google OAuth consent + callback (external-provider mode).

* GET /oauth/google/start    — redirect the user to Google's consent screen
                               (access_type=offline & prompt=consent so we get a
                               refresh token every time).
* GET /oauth/google/callback — exchange the code for tokens, read the user's
                               email from userinfo, encrypt + store the refresh
                               token in ``google_tokens``.

After this, the poller/lifecycle mint fresh access tokens from the stored
refresh token (see auth_client.py).
"""

from __future__ import annotations
from db.repository import get_google_token, upsert_google_token
import os
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from db.repository import upsert_google_token
from db.session import SessionDep

from ..crypto import encrypt
from ..oauth_config import (
    GOOGLE_AUTH_URI,
    GOOGLE_SCOPES,
    GOOGLE_TOKEN_URI,
    GOOGLE_USERINFO_URI,
    OAuthConfig,
)

router = APIRouter(prefix="/oauth/google", tags=["oauth"])


@router.get("/start")
async def start() -> RedirectResponse:
    cfg = OAuthConfig.from_env()
    if not cfg.client_id:
        raise HTTPException(status_code=500, detail="Google OAuth client not configured")
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": " ".join(GOOGLE_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
    }
    return RedirectResponse(f"{GOOGLE_AUTH_URI}?{urlencode(params)}")


@router.get("/callback")
async def callback(
    session: SessionDep,
    code: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"Google returned error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="missing authorization code")

    cfg = OAuthConfig.from_env()
    token_data = {
        "code": code,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "redirect_uri": cfg.redirect_uri,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(GOOGLE_TOKEN_URI, data=token_data)
        if token_resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"token exchange failed: {token_resp.text}",
            )
        payload = token_resp.json()
        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        scope = payload.get("scope")

        if not access_token:
            raise HTTPException(status_code=502, detail="no access_token from Google")

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if userinfo_resp.status_code >= 400:
            raise HTTPException(status_code=502, detail="userinfo lookup failed")
        email = userinfo_resp.json().get("email")

    
    if not email:
        raise HTTPException(status_code=502, detail="no email in userinfo")

    existing_token = await get_google_token(session, email)
    if not refresh_token and existing_token is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "no refresh_token returned — revoke prior access at "
                "myaccount.google.com/permissions and retry"
            ),
        )

    await upsert_google_token(
        session,
        user_id=email,
        refresh_token_enc=encrypt(refresh_token) if refresh_token else None,
        scopes=scope,
    )
    frontend = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return RedirectResponse(
        f"{frontend}/?{urlencode({'auth': 'success', 'email': email})}"
    )
