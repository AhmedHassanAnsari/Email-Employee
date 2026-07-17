"""Gmail MCP connection (taylorwilsdon/google_workspace_mcp).

The server runs in OAuth 2.1 / external-provider mode over streamable-http. We
connect per-user, injecting that user's fresh Google access token as a bearer
header so every Gmail call routes to the right mailbox.

Usage:

    async with gmail_server_for_token(token) as server:
        agent = Agent(..., mcp_servers=[server])
        ...
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from agents.mcp import MCPServerStreamableHttp, MCPServerStreamableHttpParams


def _mcp_url() -> str:
    return os.getenv("GMAIL_MCP_URL", "http://127.0.0.1:8000/mcp")


@asynccontextmanager
async def gmail_server_for_token(
    access_token: str,
) -> AsyncIterator[MCPServerStreamableHttp]:
    """Connected Gmail MCP server scoped to one user's access token."""
    server = MCPServerStreamableHttp(
        params=MCPServerStreamableHttpParams(
            url=_mcp_url(),
            headers={"Authorization": f"Bearer {access_token}"},
        ),
        cache_tools_list=True,
        name="gmail",
        client_session_timeout_seconds=30.0,
    )
    await server.connect()
    try:
        yield server
    finally:
        await server.cleanup()
