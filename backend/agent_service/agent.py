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

from .models import (
    IncomingEmail,
    RevisionContext,
    StructuredReply,
    SummaryOutput,
)

load_dotenv()

_gemini_api_key = os.getenv("GEMINI_API_KEY", "")
_gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

_external_client = AsyncOpenAI(
    api_key=_gemini_api_key or "missing-key",
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

_model = OpenAIChatCompletionsModel(
    model=_gemini_model, openai_client=_external_client
)

config = RunConfig(
    model=_model,
    model_provider=_external_client,
    tracing_disabled=True,
)


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
        "You are revising a previously rejected email reply. Use the original "
        "email, the rejected draft, and the user's feedback to produce an "
        "improved reply that addresses every concern raised, while staying "
        "professional and accurate. Return only the revised reply text.\n\n"
        f"--- Original Email ---\n{ctx.original_email}\n\n"
        f"--- Rejected Draft ---\n{ctx.rejected_draft}\n\n"
        f"--- User Feedback ---\n{ctx.user_feedback}\n"
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
            "You are an assistant drafting an email reply on the user's behalf. "
            "If useful, use the Gmail tools to read the full thread for context "
            "before drafting. Write a clear, professional reply to the incoming "
            "email. Return only the reply text — no preamble."
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
    written = await Runner.run(writer, _incoming_prompt(email), run_config=config)
    draft_text = written.final_output

    structured = await Runner.run(
        structure_agent,
        f"Draft reply to structure:\n\n{draft_text}",
        run_config=config,
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
    result = await Runner.run(
        reviewer_agent,
        "Produce the revised reply as instructed.",
        context=ctx,
        run_config=config,
    )
    return result.final_output


async def summarize(incoming: str, approved_reply: str) -> SummaryOutput:
    result = await Runner.run(
        summarizer_agent,
        f"Incoming email:\n{incoming}\n\nApproved reply:\n{approved_reply}\n\n"
        "Write the summary.",
        run_config=config,
    )
    return result.final_output
