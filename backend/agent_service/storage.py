"""Filesystem helpers for the agent's inbox / approval / Done artefacts.

Postgres is the source of truth; these on-disk JSON files are a debuggable
working area:

* ``inbox/{message_id}.json``   — written by the poller when a new email is detected.
* ``approval/{email_id}.json``  — written by ``/solve``; the draft awaiting review.
* ``Done/{email_id}.summary.json`` — audit sidecar written by ``/approve``.
"""

from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
INBOX_DIR = BASE_DIR / "inbox"
APPROVAL_DIR = BASE_DIR / "approval"
DONE_DIR = BASE_DIR / "Done"


def ensure_dirs() -> None:
    INBOX_DIR.mkdir(exist_ok=True)
    APPROVAL_DIR.mkdir(exist_ok=True)
    DONE_DIR.mkdir(exist_ok=True)


def inbox_payload_path(message_id: str) -> Path:
    return INBOX_DIR / f"{message_id}.json"


def approval_payload_path(email_id: int) -> Path:
    return APPROVAL_DIR / f"{email_id}.json"


def done_summary_path(email_id: int) -> Path:
    return DONE_DIR / f"{email_id}.summary.json"
