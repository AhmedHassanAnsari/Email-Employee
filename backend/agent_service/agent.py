"""Multi-agent email pipeline (Gemini via the OpenAI Agents SDK).

Gemini cannot combine structured output and tool calls in one agent, so the
draft path is split:

* Writer agent    — reads thread context via Gmail MCP tools; free-text draft.
* Structure agent — turns the draft into a StructuredReply (schema, no tools).
* Reviewer agent  — refines a rejected draft from in-memory feedback (free text).
* Summarizer agent — StructuredReply -> SummaryOutput for the Done/ sidecar.

The Writer is the only agent that gets ``mcp_servers``; it is constructed
per-request with the caller's connected Gmail MCP server (per-user bearer).
"""

from __future__ import annotations

import logging
import os

from agents import (
    Agent,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    RunConfig,
    Runner,
    RunContextWrapper,
)
from agents.mcp import MCPServer
from dotenv import load_dotenv
from openai import RateLimitError

from .models import (
    IncomingEmail,
    RevisionContext,
    StructuredReply,
    SummaryOutput,
)

load_dotenv()

logger = logging.getLogger(__name__)

# Owner knowledge base injected into every content-generating agent so replies
# are grounded in real facts about the account owner. The agent must answer from
# this profile and never say "I don't know" or ask the sender for details it can
# derive here (a draft that punts back for info will be rejected in review).
OWNER_PROFILE = """# Personal Profile & Knowledge Base

# TODO: Add your own details here so the AI Employee replies using YOUR data.
# This entire string is injected into every content-generating agent as the
# authoritative knowledge base about the account owner. Fill in the sections
# below (identity, background, projects, availability, FAQs, reply guidelines,
# and agent rules) with your real information. The agent answers senders from
# this profile, so anything you omit it will not know. Keep out anything you do
# not want an email recipient to see.
"""

_gemini_api_key = os.getenv("GEMINI_API_KEY1", "")
_primary_model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Tried in order after the primary when a model hits its free-tier quota.
_fallback_models = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.0-flash",
]

# Primary first, then the fallbacks (dedup, preserve order).
_model_chain: list[str] = [_primary_model] + [
    m for m in _fallback_models if m != _primary_model
]

_external_client = AsyncOpenAI(
    api_key=_gemini_api_key or "missing-key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

_models: dict[str, OpenAIChatCompletionsModel] = {
    name: OpenAIChatCompletionsModel(model=name, openai_client=_external_client)
    for name in _model_chain
}

# Default model bound to the agents at construction; per-run fallback overrides
# it via RunConfig (which takes precedence over an agent's own model).
_model = _models[_primary_model]


def _run_config(model: OpenAIChatCompletionsModel) -> RunConfig:
    return RunConfig(
        model=model,
        model_provider=_external_client,
        tracing_disabled=True,
    )


def _is_quota_error(exc: Exception) -> bool:
    """True for free-tier quota / rate-limit exhaustion (Gemini 429)."""
    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc).lower()
    return any(
        s in msg
        for s in ("quota", "resource_exhausted", "rate limit", "429")
    )


async def _run_with_fallback(agent: Agent, input, **kwargs):
    """Run ``agent`` trying each model in the chain until one isn't quota-blocked."""
    last_exc: Exception | None = None
    for name in _model_chain:
        try:
            return await Runner.run(
                agent, input, run_config=_run_config(_models[name]), **kwargs
            )
        except Exception as exc:  # noqa: BLE001 - re-raised below if non-quota
            if not _is_quota_error(exc):
                raise
            last_exc = exc
            logger.warning("Model %s quota-blocked, trying next fallback", name)
    assert last_exc is not None
    raise last_exc


# --- Structure agent (schema, no tools) --------------------------------------

structure_agent: Agent = Agent(
    name="Reply Structurer",
    instructions=(
        "You are given a drafted email reply as free text. Convert it into a "
        "StructuredReply with a clear subject line and the reply body. Do not "
        "add content — only structure what you are given. If a subject is not "
        "obvious, derive a concise one from the body."
    ),
    output_type=StructuredReply,
    model=_model,
)


# --- Summarizer agent (schema, no tools) -------------------------------------

summarizer_agent: Agent = Agent(
    name="Email Summarizer",
    instructions=(
        "Produce a concise 2-3 line summary of what the incoming email asked "
        "and what the approved reply accomplished. Return a SummaryOutput with "
        "the summary and status set to 'completed'."
    ),
    output_type=SummaryOutput,
    model=_model,
)


# --- Reviewer agent (free text, dynamic instructions) ------------------------

def _revision_instructions(
    wrapper: RunContextWrapper[RevisionContext], agent: Agent
) -> str:
    ctx = wrapper.context
    return (
        "You are the account owner's AI email assistant, revising a "
        "previously rejected email reply in the first person on their behalf. Use "
        "the original email, the rejected draft, and the user's feedback to "
        "produce an improved reply that addresses every concern raised, while "
        "staying professional and accurate. Ground the reply in the profile "
        "below — answer from it directly and do not tell the sender you lack "
        "information or ask for details the profile already covers. Return only "
        "the revised reply text.\n\n"
        f"--- Original Email ---\n{ctx.original_email}\n\n"
        f"--- Rejected Draft ---\n{ctx.rejected_draft}\n\n"
        f"--- User Feedback ---\n{ctx.user_feedback}\n\n"
        f"{OWNER_PROFILE}"
    )


reviewer_agent: Agent = Agent(
    name="Reply Reviser",
    instructions=_revision_instructions,
    model=_model,
)


# --- Writer agent factory (tools, free text) ---------------------------------

def build_writer_agent(gmail_server: MCPServer) -> Agent:
    """Writer agent bound to a per-user Gmail MCP server for thread context."""
    return Agent(
        name="Email Writer",
        instructions=(
            "You are the account owner's AI email assistant, drafting replies "
            "in the first person on their behalf. Ground every reply in the profile "
            "below — it is your authoritative knowledge base about the owner. "
            "If useful, use the Gmail tools to read the full thread for context "
            "before drafting. Write a clear, professional reply to the incoming "
            "email, following the Email Reply Guidelines and AI Agent Rules in "
            "the profile.\n\n"
            "Do NOT tell the sender you don't have information or ask them to "
            "supply details that are already answered in the profile — answer "
            "directly from it. Only defer when a request genuinely requires "
            "the owner's personal decision, and then say it has been forwarded "
            "for their review (per the Response Policy). Never invent facts, "
            "achievements, or commitments not in the profile.\n\n"
            "Return only the reply text — no preamble.\n\n"
            f"{OWNER_PROFILE}"
        ),
        mcp_servers=[gmail_server],
        model=_model,
    )


# --- Orchestration -----------------------------------------------------------

def _incoming_prompt(email: IncomingEmail) -> str:
    return (
        f"Incoming email to reply to:\n"
        f"From: {email.from_addr or 'unknown'}\n"
        f"Subject: {email.subject or '(no subject)'}\n"
        f"Thread ID: {email.thread_id or '(none)'}\n\n"
        f"{email.body}\n\n"
        "Draft a reply."
    )


async def draft_reply(
    email: IncomingEmail, gmail_server: MCPServer
) -> StructuredReply:
    """Writer (with tools) -> Structure. Returns the structured reply to review."""
    writer = build_writer_agent(gmail_server)
    written = await _run_with_fallback(writer, _incoming_prompt(email))
    draft_text = written.final_output

    structured = await _run_with_fallback(
        structure_agent,
        f"Draft reply to structure:\n\n{draft_text}",
    )
    reply: StructuredReply = structured.final_output
    if email.thread_id and not reply.in_reply_to:
        reply.in_reply_to = email.thread_id
    return reply


async def revise_reply(
    original_email: str, rejected_draft: str, user_feedback: str
) -> str:
    """Reviewer refine step — stateless, context passed in memory."""
    ctx = RevisionContext(
        original_email=original_email,
        rejected_draft=rejected_draft,
        user_feedback=user_feedback,
    )
    result = await _run_with_fallback(
        reviewer_agent,
        "Produce the revised reply as instructed.",
        context=ctx,
    )
    return result.final_output


async def summarize(incoming: str, approved_reply: str) -> SummaryOutput:
    result = await _run_with_fallback(
        summarizer_agent,
        f"Incoming email:\n{incoming}\n\nApproved reply:\n{approved_reply}\n\n"
        "Write the summary.",
    )
    return result.final_output
