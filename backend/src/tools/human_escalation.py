"""Day 7 Phase 3 — Human escalation tool: create_escalation.

Creates a REAL human-help escalation request in PostgreSQL ONLY when the caller
has explicitly given permission to share a short summary with a human support
person. Consent is enforced in the tool itself — no database row is ever
written unless `consent_confirmed` is true — so the guarantee does not depend
on the LLM or the system prompt alone.

Honesty contract:
- On success the tool returns the reference ID (ESC-XXXXXXXX) to quote to the
  caller, and an honest next step (a human can review the summary; there is no
  guaranteed immediate response).
- On failure (database unreachable, reference-ID collisions exhausted, invalid
  arguments) the tool returns a structured error WITHOUT a reference ID, so
  the agent can never pretend a request was created.

Privacy:
- The database only ever receives the short human-help summary
  (`what_happened`, `agent_action`) — never credentials (passwords, OTPs,
  PINs, account numbers, tokens) and never full conversation transcripts.
- All free-text inputs are truncated to bounded lengths as defense in depth,
  and the tool's parameter surface exposes no credential fields.
"""

import json
import logging
import secrets
from typing import Optional

import asyncpg
from livekit.agents import RunContext, function_tool

from db import save_escalation

logger = logging.getLogger("human_escalation_tool")

# Day 7 value contracts (mirrors the escalation_requests schema).
ALLOWED_REASONS = {"red_flag_symptom", "diagnosis_request"}
ALLOWED_URGENCIES = {"low", "medium", "high", "emergency"}

# Conservative keyword sets used ONLY to inject a per-turn instruction (offer
# human help + ask consent). They never create an escalation by themselves —
# consent is still mandatory. Aligned with the existing triage critical
# keywords and the prompt's emergency script.
RED_FLAG_KEYWORDS = [
    "chest pain",
    "heart attack",
    "difficulty breathing",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "short of breath",
    "breathlessness",
    "breathless",
    "unconscious",
    "passed out",
    "fainted",
    "collapse",
    "collapsed",
    "uncontrolled bleeding",
    "severe bleeding",
    "bleeding heavily",
    "stroke",
    "paralysis",
    "seizure",
    "severe",
]

DIAGNOSIS_REQUEST_KEYWORDS = [
    "diagnos",
    "what disease",
    "which disease",
    "what illness",
    "what condition",
    "tell me what i have",
    "बीमारी",
    "रोग",
    "રોગ",
]


def detect_escalation_trigger(text):
    """Return the Day 7 trigger for a user turn: 'red_flag_symptom',
    'diagnosis_request', or None for normal turns.

    Used ONLY to decide whether to inject a per-turn instruction (give
    safety guidance AND offer human help with a consent question). It never
    creates an escalation — explicit caller consent is still required.
    """
    if not text:
        return None
    lower = text.lower()
    # Red-flag takes precedence: a caller who asks for a diagnosis WHILE
    # describing a red flag must still get the emergency flow first.
    if any(kw in lower for kw in RED_FLAG_KEYWORDS):
        return "red_flag_symptom"
    if any(kw in lower for kw in DIAGNOSIS_REQUEST_KEYWORDS):
        return "diagnosis_request"
    return None

# Bounded retry for reference-ID collisions — never retry indefinitely.
MAX_REFERENCE_RETRIES = 3

# Defense-in-depth size caps: only the short summary ever reaches the DB.
MAX_SUMMARY_LENGTH = 500
MAX_ACTION_LENGTH = 300
MAX_LANGUAGE_LENGTH = 32
MAX_FOLLOW_UP_LENGTH = 64
MAX_USER_ID_LENGTH = 255


def generate_reference_id() -> str:
    """Return a collision-resistant reference ID of the form ESC-XXXXXXXX."""
    return f"ESC-{secrets.token_hex(4).upper()}"


def _clean_text(value, max_length: int) -> str:
    """Strip whitespace and truncate to a bounded length (None-safe)."""
    if not value:
        return ""
    return str(value).strip()[:max_length]


def _success_result(reference_id: str, reason: str, urgency: str) -> str:
    return json.dumps(
        {
            "status": "ok",
            "reference_id": reference_id,
            "reason": reason,
            "urgency": urgency,
            "message": (
                "Human support request created. A human support person can review "
                "the summary. There is no guaranteed immediate response."
            ),
        },
        ensure_ascii=False,
    )


def _no_consent_result() -> str:
    return json.dumps(
        {
            "status": "no_consent",
            "reference_id": None,
            "message": (
                "No escalation request was created because the caller did not give "
                "explicit permission to share their information with a human."
            ),
        },
        ensure_ascii=False,
    )


def _error_result(code: str, message: str) -> str:
    return json.dumps(
        {"status": "error", "code": code, "message": message},
        ensure_ascii=False,
    )


async def create_escalation_impl(
    user_id: str,
    reason: str,
    what_happened: str,
    agent_action: Optional[str] = None,
    urgency: str = "medium",
    language: Optional[str] = None,
    preferred_follow_up: Optional[str] = None,
    consent_confirmed: bool = False,
) -> str:
    """Core implementation — separated from the LiveKit decorator for testability."""
    logger.info(
        "[HUMAN ESCALATION] request reason=%r user_id=%r consent=%s",
        reason,
        user_id,
        consent_confirmed,
    )

    # 1. CONSENT IS MANDATORY — enforced here, in the tool itself. No consent
    #    means no database call and no row, no matter what the caller said.
    #    Strict `is not True` (fail-closed): a truthy non-boolean value such as
    #    the string "false" must NEVER be treated as consent.
    if consent_confirmed is not True:
        return _no_consent_result()

    # 2. Day 7 value contracts.
    reason = (reason or "").strip().lower()
    if reason not in ALLOWED_REASONS:
        return _error_result(
            "INVALID_ARGUMENT",
            f"reason must be one of {sorted(ALLOWED_REASONS)}.",
        )
    urgency = (urgency or "").strip().lower()
    if urgency not in ALLOWED_URGENCIES:
        return _error_result(
            "INVALID_ARGUMENT",
            f"urgency must be one of {sorted(ALLOWED_URGENCIES)}.",
        )

    # 3. Only the short summary — bounded length, never a full transcript.
    what_happened = _clean_text(what_happened, MAX_SUMMARY_LENGTH)
    if not what_happened:
        return _error_result(
            "INVALID_ARGUMENT", "what_happened must be a non-empty short summary."
        )
    agent_action = _clean_text(agent_action, MAX_ACTION_LENGTH) or None
    language = _clean_text(language, MAX_LANGUAGE_LENGTH) or None
    preferred_follow_up = _clean_text(preferred_follow_up, MAX_FOLLOW_UP_LENGTH) or None
    user_id = _clean_text(user_id, MAX_USER_ID_LENGTH)
    if not user_id:
        return _error_result("INVALID_ARGUMENT", "user_id must not be empty.")

    # 4. Persist with bounded retry on reference-ID collisions. A fresh ID is
    #    generated for every attempt so we never reuse a collided reference.
    for attempt in range(1, MAX_REFERENCE_RETRIES + 1):
        reference_id = generate_reference_id()
        try:
            record = await save_escalation(
                reference_id=reference_id,
                user_id=user_id,
                reason=reason,
                what_happened=what_happened,
                agent_action=agent_action,
                urgency=urgency,
                language=language,
                preferred_follow_up=preferred_follow_up,
                consent_confirmed=True,
            )
        except asyncpg.UniqueViolationError:
            logger.warning(
                "[HUMAN ESCALATION] reference_id collision "
                "attempt=%d/%d retrying with a fresh ID",
                attempt,
                MAX_REFERENCE_RETRIES,
            )
            continue
        except Exception as exc:  # e.g. connection dropped mid-insert
            logger.error("[HUMAN ESCALATION] save failed: %s", exc)
            return _error_result(
                "DB_UNAVAILABLE",
                "The human support request could not be created right now. "
                "Tell the caller it was NOT submitted, and suggest trying again "
                "shortly.",
            )

        if record is None:
            # save_escalation returns None when the database is unreachable.
            return _error_result(
                "DB_UNAVAILABLE",
                "The human support request could not be created right now. "
                "Tell the caller it was NOT submitted, and suggest trying again "
                "shortly.",
            )

        logger.info(
            "[HUMAN ESCALATION] created reference_id=%s reason=%s urgency=%s "
            "user_id=%s",
            reference_id,
            reason,
            urgency,
            user_id,
        )
        return _success_result(reference_id, reason, urgency)

    logger.error(
        "[HUMAN ESCALATION] failed after %d attempts (reference_id collisions)",
        MAX_REFERENCE_RETRIES,
    )
    return _error_result(
        "DB_WRITE_FAILED",
        "The human support request could not be created right now. "
        "Tell the caller it was NOT submitted, and suggest trying again shortly.",
    )


class HumanEscalationTools:
    @function_tool
    async def create_escalation(
        self,
        context: RunContext,
        user_id: str,
        reason: str,
        what_happened: str,
        agent_action: str = "",
        urgency: str = "medium",
        language: str = "",
        preferred_follow_up: str = "",
        consent_confirmed: bool = False,
    ) -> str:
        """Create a human-help escalation request for a caller with a RED-FLAG symptom or who asked for a diagnosis.

        USE THIS TOOL ONLY when BOTH of these are true:
        1. The situation is one of the two Day 7 reasons:
           - "red_flag_symptom": the caller described a serious red-flag health
             symptom (e.g. severe chest pain, difficulty breathing,
             unconsciousness, severe bleeding, stroke-like symptoms). Give the
             emergency guidance (call 112/108) FIRST, then offer human help.
           - "diagnosis_request": the caller asked you to diagnose them. Refuse
             to diagnose and offer human assistance instead.
        2. The caller EXPLICITLY said YES to sharing a short summary with a
           human support person after you asked for their permission.

        CRITICAL RULES:
        - NEVER call this tool for normal conversations or general health
          questions, and NEVER merely because a red flag was detected.
        - NEVER call this tool before asking permission and getting an explicit
          YES — set consent_confirmed=True ONLY after the caller says yes.
          If the caller declines, DO NOT call this tool at all.
        - what_happened must be a SHORT summary (a few sentences max) of what
          the caller told you — NOT the full transcript. Never include
          passwords, OTPs, PINs, account numbers, or tokens.
        - On success the tool returns a reference ID (ESC-XXXXXXXX) to quote to
          the caller. On failure it returns an explicit error with no reference
          ID — never claim a request was created without a reference ID, and
          never promise an immediate callback or guaranteed response time.

        Args:
            user_id: The caller's unique ID (provided to you when the call starts).
            reason: One of "red_flag_symptom" or "diagnosis_request".
            what_happened: Short summary of what the caller reported (a few sentences max).
            agent_action: What Saathi already advised or checked for this caller.
            urgency: One of "low", "medium", "high", "emergency".
            language: The caller's language (e.g. English, Hindi, Gujarati).
            preferred_follow_up: How the caller prefers follow-up, if they said (e.g. SMS, phone call).
            consent_confirmed: MUST be True (the caller explicitly said yes). If False, no request is created.
        """
        logger.info(
            "[HUMAN ESCALATION] create_escalation reason=%r user_id=%r",
            reason,
            user_id,
        )
        return await create_escalation_impl(
            user_id=user_id,
            reason=reason,
            what_happened=what_happened,
            agent_action=agent_action,
            urgency=urgency,
            language=language,
            preferred_follow_up=preferred_follow_up,
            consent_confirmed=consent_confirmed,
        )
