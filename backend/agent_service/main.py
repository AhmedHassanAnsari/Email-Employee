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
from fastapi.middleware.cors import CORSMiddleware

from db.session import get_engine, get_sessionmaker
from .storage import ensure_dirs

load_dotenv()

# Vite dev server origins allowed to call the API from the browser.
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv(
        "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


from .routers import lifecycle, oauth  # noqa: E402

app.include_router(lifecycle.router)
app.include_router(oauth.router)
