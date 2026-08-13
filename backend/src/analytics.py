"""Day 8 — Call analytics tracker.

Deterministically records the outcome of every voice call (browser or SIP)
from application events only — NEVER an LLM judgment.

Success conditions (Health Access track — approved definition):
  1. `create_escalation` returns {"status": "ok", "reference_id": ...}
     → success (escalation). Consent is already enforced inside the tool, so a
     successful escalation row means explicit consent was given.
  2. `find_nearby_health_facilities` returns {"status": "ok"}
     → success (guidance — real facilities were delivered).
  3. `analyze_symptoms` executes successfully (its output is always a triage
     outcome) → success (guidance).
  4. `find_emergency_contact` executes successfully (its output is always a
     contact number) → success (guidance).
  5. A substantive assistant reply (>= MIN_GUIDANCE_TEXT_LENGTH characters) is
     spoken after at least one real user message → success (guidance). The
     opening greeting is deliberately excluded because it precedes any user
     message.

Anything else at end of call is FAILED with a deterministic failure_reason
derived from the session close reason and the conversation state.

Fail-soft guarantee: the tracker NEVER raises and NEVER blocks the call.
Every database write is guarded; on failure it logs and moves on.

Privacy: the analytics row stores only metadata (opaque caller id, channel,
timestamps, duration, outcome, escalation reference, detected language) —
never transcripts, medical details, passwords, OTPs, PINs, or account numbers.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone

from livekit.agents import (
    AgentSession,
    ChatMessage,
    CloseEvent,
    CloseReason,
    ConversationItemAddedEvent,
    FunctionToolsExecutedEvent,
)

from db import finalize_call_analytics, start_call_analytics

logger = logging.getLogger("analytics")

# Minimum length of an assistant message to count as substantive guidance.
MIN_GUIDANCE_TEXT_LENGTH = 20

GUIDANCE_MARKER_CONVERSATION = "conversation"
GUIDANCE_MARKER_FACILITY = "facility_lookup"
GUIDANCE_MARKER_TRIAGE = "triage"
GUIDANCE_MARKER_EMERGENCY_CONTACT = "emergency_contact"

# Tool name -> guidance marker. The two plain-text tools always produce a
# useful result when they execute; the facility tool is only a success when its
# JSON result carries status "ok".
GUIDANCE_TOOLS = {
    "find_nearby_health_facilities": GUIDANCE_MARKER_FACILITY,
    "analyze_symptoms": GUIDANCE_MARKER_TRIAGE,
    "find_emergency_contact": GUIDANCE_MARKER_EMERGENCY_CONTACT,
}
FACILITY_TOOL = "find_nearby_health_facilities"
ESCALATION_TOOL = "create_escalation"

OUTCOME_SUCCESS = "success"
OUTCOME_FAILED = "failed"
SUCCESS_TYPE_GUIDANCE = "guidance"
SUCCESS_TYPE_ESCALATION = "escalation"
FAILURE_REASON_ERROR = "error"
FAILURE_REASON_NO_RESPONSE = "no_response"
FAILURE_REASON_NO_SUCCESS = "no_success_condition"


def _parse_json(text: str):
    """Safely parse a tool-output JSON string. Returns a dict or None."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def resolve_outcome(
    *,
    escalation_marker: str | None,
    guidance_marker: str | None,
    user_messages: int,
    close_reason: str = "",
):
    """Resolve the final call outcome deterministically.

    Priority:
      1. escalation created      -> success (escalation)
      2. safe guidance delivered -> success (guidance)
      3. session error           -> failed (error)
      4. no user message at all  -> failed (no_response)
      5. otherwise               -> failed (no_success_condition)

    Returns (outcome, success_type, failure_reason, escalated_ref).
    """
    if escalation_marker:
        return (
            OUTCOME_SUCCESS,
            SUCCESS_TYPE_ESCALATION,
            None,
            escalation_marker,
        )
    if guidance_marker:
        return OUTCOME_SUCCESS, SUCCESS_TYPE_GUIDANCE, None, None
    if close_reason == CloseReason.ERROR.value:
        return OUTCOME_FAILED, None, FAILURE_REASON_ERROR, None
    if user_messages <= 0:
        return OUTCOME_FAILED, None, FAILURE_REASON_NO_RESPONSE, None
    return OUTCOME_FAILED, None, FAILURE_REASON_NO_SUCCESS, None


class CallAnalyticsTracker:
    """Tracks one call's deterministic outcome and persists it to PostgreSQL.

    Usage (wired in the agent jobs during Phase 3):
        tracker = CallAnalyticsTracker(call_id=room.name, user_id=caller_id,
                                       channel="browser", language=detected)
        await tracker.record_start()
        tracker.wire(session)          # subscribes to session events
        # ... call runs ...
        await tracker.finalize()       # idempotent; also triggered by "close"

    Fail-soft: every database call is guarded so analytics can never break or
    delay a live voice call.
    """

    def __init__(
        self,
        call_id: str,
        user_id: str = "",
        channel: str = "browser",
        language: str = "",
    ) -> None:
        self.call_id = call_id
        self.user_id = user_id
        self.channel = channel if channel in ("browser", "sip") else "browser"
        self.language = language
        self._started_at = time.time()
        self._finalized = False
        self._escalation_marker: str | None = None
        self._guidance_marker: str | None = None
        self._user_messages = 0
        self._close_reason = ""

    # -- read-only state (useful for tests / debugging) ----------------------

    @property
    def escalation_marker(self) -> str | None:
        return self._escalation_marker

    @property
    def guidance_marker(self) -> str | None:
        return self._guidance_marker

    @property
    def user_messages(self) -> int:
        return self._user_messages

    @property
    def finalized(self) -> bool:
        return self._finalized

    # -- lifecycle -----------------------------------------------------------

    async def record_start(self) -> None:
        """Persist the call-start row. Fail-soft: never raises."""
        try:
            await start_call_analytics(
                call_id=self.call_id,
                user_id=self.user_id,
                channel=self.channel,
                language=self.language or None,
            )
        except Exception as exc:  # defense in depth — db helper is also guarded
            logger.error(
                "[ANALYTICS] record_start failed call_id=%s reason=%s",
                self.call_id,
                exc,
            )

    def wire(self, session: AgentSession) -> None:
        """Subscribe to the deterministic session events that drive outcomes."""
        session.on("function_tools_executed", self._on_function_tools_executed)
        session.on("conversation_item_added", self._on_conversation_item_added)
        session.on("close", self._on_close)

    async def finalize(self, close_reason: str = "") -> None:
        """Resolve and persist the final outcome. Idempotent: runs once."""
        if self._finalized:
            return
        self._finalized = True

        try:
            outcome, success_type, failure_reason, escalated_ref = resolve_outcome(
                escalation_marker=self._escalation_marker,
                guidance_marker=self._guidance_marker,
                user_messages=self._user_messages,
                close_reason=close_reason or self._close_reason,
            )
            ended_at = datetime.now(timezone.utc)
            duration_seconds = max(0, int(time.time() - self._started_at))
            await finalize_call_analytics(
                call_id=self.call_id,
                outcome=outcome,
                success_type=success_type,
                failure_reason=failure_reason,
                escalated_ref=escalated_ref,
                ended_at=ended_at,
                duration_seconds=duration_seconds,
            )
        except Exception as exc:  # defense in depth — db helper is also guarded
            logger.error(
                "[ANALYTICS] finalize failed call_id=%s reason=%s",
                self.call_id,
                exc,
            )

    # -- event handlers (synchronous, never raise) ---------------------------

    def _on_function_tools_executed(self, ev: FunctionToolsExecutedEvent) -> None:
        try:
            for call, output in ev.zipped():
                name = (call.name or "").strip()
                if not name or output is None or output.is_error:
                    continue
                text = (output.output or "").strip()
                if not text:
                    continue
                if name == ESCALATION_TOOL:
                    self._maybe_mark_escalation(text)
                elif name in GUIDANCE_TOOLS:
                    self._maybe_mark_guidance(name, text)
        except Exception:
            logger.exception("[ANALYTICS] function_tools_executed handler failed")

    def _on_conversation_item_added(self, ev: ConversationItemAddedEvent) -> None:
        try:
            item = ev.item
            if not isinstance(item, ChatMessage):
                return
            if item.role == "user":
                if (item.text_content or "").strip():
                    self._user_messages += 1
            elif item.role == "assistant":
                text = (item.text_content or "").strip()
                # The opening greeting precedes any user message, so it can
                # never count as guidance.
                if self._user_messages > 0 and len(text) >= MIN_GUIDANCE_TEXT_LENGTH:
                    self._set_guidance(GUIDANCE_MARKER_CONVERSATION)
        except Exception:
            logger.exception("[ANALYTICS] conversation_item_added handler failed")

    def _on_close(self, ev: CloseEvent) -> None:
        try:
            reason = getattr(getattr(ev, "reason", None), "value", None) or ""
        except Exception:
            reason = ""
        self._close_reason = reason
        try:
            asyncio.get_running_loop().create_task(self.finalize(close_reason=reason))
        except RuntimeError:
            logger.error(
                "[ANALYTICS] no running loop to schedule finalize call_id=%s",
                self.call_id,
            )

    # -- internal helpers ----------------------------------------------------

    def _maybe_mark_escalation(self, text: str) -> None:
        data = _parse_json(text)
        if (
            data
            and data.get("status") == "ok"
            and (data.get("reference_id") or "").strip()
        ):
            self._escalation_marker = str(data["reference_id"]).strip()[:32]

    def _maybe_mark_guidance(self, tool_name: str, text: str) -> None:
        if tool_name == FACILITY_TOOL:
            # Only a REAL successful lookup counts; structured error results do
            # not (they carry no `retrieved_at` and must never count).
            data = _parse_json(text)
            if data and data.get("status") == "ok":
                self._set_guidance(GUIDANCE_TOOLS[tool_name])
        else:
            # analyze_symptoms / find_emergency_contact always produce a useful
            # result when executed — a non-empty output counts as delivered.
            self._set_guidance(GUIDANCE_TOOLS[tool_name])

    def _set_guidance(self, marker: str) -> None:
        if self._guidance_marker is None:
            self._guidance_marker = marker
