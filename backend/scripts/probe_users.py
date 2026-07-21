import asyncio
from dotenv import load_dotenv
load_dotenv("../.env")
from agent_service.auth_client import AuthClient

async def main():
    users = await AuthClient().list_users()
    print("google_tokens users:", users)

asyncio.run(main())
