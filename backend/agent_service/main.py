"""FastAPI agent service — email lifecycle endpoints.

Endpoints (defined in routers/lifecycle.py):
* POST /emails/{id}/solve    — run the pipeline, write approval artefact, notify (approval)
* POST /emails/{id}/approve  — send the reply in-thread via MCP, write Done summary, notify (done)
* POST /emails/{id}/reject   — refine the draft from feedback, back to approval

No inbox notification: a detected email goes straight to /solve.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from db.session import get_engine, get_sessionmaker
from .storage import ensure_dirs

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_dirs()
    engine = get_engine(os.environ["DATABASE_URL"])
    app.state.engine = engine
    app.state.sessionmaker = get_sessionmaker(engine)
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="AI Email Employee — Agent Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


from .routers import lifecycle, oauth  # noqa: E402

app.include_router(lifecycle.router)
app.include_router(oauth.router)
