import asyncio, json, urllib.request
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient
from agent_service.gmail_mcp import gmail_server_for_token
from email_monitor import _tool_text

async def main():
    a = AuthClient()
    u = (await a.list_users())[0]
    print("DB user_id (stored at consent):", u)
    t = await a.get_access_token(u)
    # Ask Google who this token belongs to
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {t}"},
    )
    info = json.loads(urllib.request.urlopen(req, None, 30).read())
    print("TOKEN really resolves to:", info.get("email"), "| verified:", info.get("email_verified"))
    # Pull To: header of a detected email
    async with gmail_server_for_token(t) as g:
        c = await g.call_tool("get_gmail_messages_content_batch",
            {"message_ids": ["19f07bc626a1402c"], "format": "full"})
        block = _tool_text(c)
        for line in block.splitlines():
            if line.startswith(("Message ID:", "Subject:", "From:", "To:", "Date:")):
                print("  ", line)

asyncio.run(main())
