"""WhatsApp MCP server wrapping the Twilio Sandbox HTTP API.

Loads credentials via python-dotenv. Never logs or returns credential values.
Exposes a single tool: ``send_whatsapp(body)``.
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "")
USER_WHATSAPP_TO = os.getenv("USER_WHATSAPP_TO", "")

mcp = FastMCP("whatsapp-notify")


def _credentials_complete() -> bool:
    return bool(
        TWILIO_ACCOUNT_SID
        and TWILIO_AUTH_TOKEN
        and TWILIO_WHATSAPP_FROM
        and USER_WHATSAPP_TO
    )


async def _fetch_message_status(sid: str) -> dict[str, Any]:
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages/{sid}.json"
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
    if r.status_code >= 400:
        return {"status": "unknown", "error_code": None, "error_message": f"HTTP {r.status_code}"}
    p = r.json()
    return {
        "status": p.get("status", ""),
        "error_code": p.get("error_code"),
        "error_message": p.get("error_message"),
    }


@mcp.tool()
async def send_whatsapp(body: str) -> dict[str, Any]:
    """Send a WhatsApp message to the configured recipient via Twilio Sandbox.

    Posts the message, then performs a single status verification fetch to
    surface immediate delivery failures. Does not retry.
    """
    if not _credentials_complete():
        return {"status": "error", "error": "WhatsApp disabled: Twilio credentials not configured"}
    if not body or not body.strip():
        return {"status": "error", "error": "Empty message body"}

    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
    data = {"From": TWILIO_WHATSAPP_FROM, "To": USER_WHATSAPP_TO, "Body": body}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                url, data=data, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            )
        if response.status_code >= 400:
            try:
                err_msg = response.json().get("message", f"HTTP {response.status_code}")
            except Exception:
                err_msg = f"HTTP {response.status_code}"
            return {"status": "error", "error": err_msg}

        payload = response.json()
        sid = payload.get("sid", "")
        initial_status = payload.get("status", "")

        verified = {"status": initial_status, "error_code": None, "error_message": None}
        if sid:
            try:
                verified = await _fetch_message_status(sid)
            except Exception:
                pass

        final_status = verified.get("status", initial_status)
        error_code = verified.get("error_code")
        error_message = verified.get("error_message")

        if final_status == "failed" or error_code:
            reason = f"{error_code}: {error_message or 'no message'}".strip(": ")
            return {"status": "failed", "sid": sid, "twilio_status": final_status, "reason": reason}

        return {"status": "sent", "sid": sid, "twilio_status": final_status}
    except Exception as exc:
        return {"status": "error", "error": f"Request failed: {type(exc).__name__}"}


if __name__ == "__main__":
    if not _credentials_complete():
        print("WhatsApp MCP: credentials incomplete; tool will return errors", file=sys.stderr)
    mcp.run()
