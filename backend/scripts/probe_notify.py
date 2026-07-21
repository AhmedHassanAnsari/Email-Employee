import asyncio
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.notify import notify, NotificationEvent, _credentials_present, _get_agent

async def main():
    print("credentials_present:", _credentials_present())
    agent = await _get_agent()
    print("agent built:", agent is not None)
    if agent:
        # inspect the tools the MCP stdio server exposed
        for srv in agent.mcp_servers:
            try:
                tools = await srv.list_tools()
                print("MCP tools:", [t.name for t in tools])
            except Exception as e:
                print("list_tools error:", type(e).__name__, e)
    ok = await notify(NotificationEvent(event_type="approval", email_id=10, subject="Re: Security alert"))
    print("notify returned:", ok)

asyncio.run(main())
