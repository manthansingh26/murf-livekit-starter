"""Day 8 — call analytics tracker tests.

Fast deterministic unit tests cover:
 1. outcome resolution priority (escalation / guidance / failed / error /
    no_response)
 2. function_tools_executed parsing for all four tools (+ failure statuses)
 3. conversational guidance via conversation_item_added (greeting excluded)
 4. full event -> finalize flow with the database boundary mocked
 5. fail-soft: database failures never raise and never break the "call"
 6. idempotent finalize (double finalize persists exactly once)
 7. privacy: the analytics surface has no sensitive fields/columns
 8. live DB roundtrip (start -> finalize -> summary), skips if no PostgreSQL
"""

import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from dotenv import load_dotenv
from livekit.agents import (
    AgentSession,
    ChatMessage,
    CloseEvent,
    CloseReason,
    ConversationItemAddedEvent,
    FunctionCall,
    FunctionCallOutput,
    FunctionToolsExecutedEvent,
)

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

import analytics as analytics_module  # noqa: E402
from analytics import (  # noqa: E402
    FAILURE_REASON_ERROR,
    FAILURE_REASON_NO_RESPONSE,
    FAILURE_REASON_NO_SUCCESS,
    MIN_GUIDANCE_TEXT_LENGTH,
    OUTCOME_FAILED,
    OUTCOME_SUCCESS,
    SUCCESS_TYPE_ESCALATION,
    SUCCESS_TYPE_GUIDANCE,
    CallAnalyticsTracker,
    resolve_outcome,
)
from db import (  # noqa: E402
    finalize_call_analytics,
    get_call_analytics_summary,
    get_db_pool,
    init_db,
    start_call_analytics,
)

FORBIDDEN_FIELDS = {
    "password",
    "otp",
    "pin",
    "account",
    "token",
    "transcript",
    "pan",
    "aadhaar",
    "credit_card",
    "medical",
    "what_happened",
}


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _tool_event(name: str, output: str, *, is_error: bool = False):
    """Build a FunctionToolsExecutedEvent for a single tool call."""
    call = FunctionCall(call_id=f"call_{name}", name=name, arguments="{}")
    out = FunctionCallOutput(
        call_id=call.call_id, name=name, output=output, is_error=is_error
    )
    return FunctionToolsExecutedEvent(
        function_calls=[call], function_call_outputs=[out]
    )


def _user_message(text: str):
    return ConversationItemAddedEvent(item=ChatMessage(role="user", content=[text]))


def _assistant_message(text: str):
    return ConversationItemAddedEvent(
        item=ChatMessage(role="assistant", content=[text])
    )


# ---------------------------------------------------------------------------
# 1. Outcome resolution
# ---------------------------------------------------------------------------


def test_resolve_escalation_wins_over_guidance():
    outcome, success_type, failure_reason, ref = resolve_outcome(
        escalation_marker="ESC-ABC12345",
        guidance_marker="triage",
        user_messages=2,
    )
    assert outcome == OUTCOME_SUCCESS
    assert success_type == SUCCESS_TYPE_ESCALATION
    assert failure_reason is None
    assert ref == "ESC-ABC12345"


def test_resolve_guidance_success():
    outcome, success_type, failure_reason, ref = resolve_outcome(
        escalation_marker=None, guidance_marker="facility_lookup", user_messages=1
    )
    assert outcome == OUTCOME_SUCCESS
    assert success_type == SUCCESS_TYPE_GUIDANCE
    assert failure_reason is None
    assert ref is None


def test_resolve_no_markers_is_failed():
    outcome, success_type, failure_reason, ref = resolve_outcome(
        escalation_marker=None, guidance_marker=None, user_messages=3
    )
    assert outcome == OUTCOME_FAILED
    assert success_type is None
    assert failure_reason == FAILURE_REASON_NO_SUCCESS
    assert ref is None


def test_resolve_session_error_is_failed():
    outcome, _, failure_reason, _ = resolve_outcome(
        escalation_marker=None,
        guidance_marker=None,
        user_messages=1,
        close_reason=CloseReason.ERROR.value,
    )
    assert outcome == OUTCOME_FAILED
    assert failure_reason == FAILURE_REASON_ERROR


def test_resolve_no_user_messages_is_no_response():
    outcome, _, failure_reason, _ = resolve_outcome(
        escalation_marker=None, guidance_marker=None, user_messages=0
    )
    assert outcome == OUTCOME_FAILED
    assert failure_reason == FAILURE_REASON_NO_RESPONSE


# ---------------------------------------------------------------------------
# 2. function_tools_executed parsing
# ---------------------------------------------------------------------------


def test_escalation_ok_marks_escalation_success():
    tracker = CallAnalyticsTracker(call_id="room-x", user_id="u1", channel="browser")
    tracker._on_function_tools_executed(
        _tool_event(
            "create_escalation",
            json.dumps({"status": "ok", "reference_id": "ESC-1A2B3C4D"}),
        )
    )
    assert tracker.escalation_marker == "ESC-1A2B3C4D"
    assert tracker.guidance_marker is None


def test_escalation_error_result_never_marks_success():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event(
            "create_escalation",
            json.dumps({"status": "error", "code": "DB_UNAVAILABLE"}),
        )
    )
    assert tracker.escalation_marker is None
    assert tracker.guidance_marker is None


def test_escalation_without_reference_id_never_marks_success():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event("create_escalation", json.dumps({"status": "ok"}))
    )
    assert tracker.escalation_marker is None


def test_facility_ok_marks_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event(
            "find_nearby_health_facilities",
            json.dumps({"status": "ok", "count": 3}),
        )
    )
    assert tracker.guidance_marker == "facility_lookup"


def test_facility_error_result_never_marks_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event(
            "find_nearby_health_facilities",
            json.dumps({"status": "error", "code": "SERVICE_UNAVAILABLE"}),
        )
    )
    assert tracker.guidance_marker is None


def test_triage_tool_counts_as_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event(
            "analyze_symptoms",
            "LOW/MODERATE: Suggest resting, monitoring symptoms, and visiting a local clinic if they worsen.",
        )
    )
    assert tracker.guidance_marker == "triage"


def test_emergency_contact_tool_counts_as_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event("find_emergency_contact", "Ambulance number is 108")
    )
    assert tracker.guidance_marker == "emergency_contact"


def test_tool_exception_output_ignored():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event("find_nearby_health_facilities", "boom", is_error=True)
    )
    assert tracker.guidance_marker is None


def test_unrelated_tool_is_ignored():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event("some_other_tool", json.dumps({"status": "ok"}))
    )
    assert tracker.guidance_marker is None
    assert tracker.escalation_marker is None


def test_malformed_tool_output_never_marks_success():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_function_tools_executed(
        _tool_event("find_nearby_health_facilities", "not json at all {{{")
    )
    assert tracker.guidance_marker is None


# ---------------------------------------------------------------------------
# 3. Conversational guidance (greeting excluded)
# ---------------------------------------------------------------------------


def test_greeting_never_counts_as_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_conversation_item_added(
        _assistant_message(
            "Namaste! I am Saathi, your health assistant. How are you feeling today?"
        )
    )
    assert tracker.user_messages == 0
    assert tracker.guidance_marker is None


def test_substantive_reply_after_user_message_counts():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_conversation_item_added(
        _user_message("I have had a mild fever and headache since yesterday.")
    )
    tracker._on_conversation_item_added(
        _assistant_message(
            "Thank you for telling me. For a mild fever, please rest and drink plenty of fluids."
        )
    )
    assert tracker.user_messages == 1
    assert tracker.guidance_marker == "conversation"


def test_short_reply_does_not_count_as_guidance():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_conversation_item_added(_user_message("Hi"))
    tracker._on_conversation_item_added(_assistant_message("Hello!"))
    assert tracker.user_messages == 1
    assert tracker.guidance_marker is None


def test_reply_before_any_user_message_never_counts():
    tracker = CallAnalyticsTracker(call_id="room-x")
    tracker._on_conversation_item_added(
        _assistant_message(
            "This is a very long pre-greeting message that exceeds twenty chars."
        )
    )
    assert tracker.guidance_marker is None


def test_min_guidance_length_constant_is_reasonable():
    assert MIN_GUIDANCE_TEXT_LENGTH >= 15, "threshold must not be trivially small"


# ---------------------------------------------------------------------------
# 4. Full event -> finalize flow (database boundary mocked)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flow_escalation_success(monkeypatch):
    calls = []

    async def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(analytics_module, "finalize_call_analytics", fake_finalize)

    tracker = CallAnalyticsTracker(call_id="room-e", user_id="u", channel="browser")
    tracker._on_function_tools_executed(
        _tool_event(
            "create_escalation",
            json.dumps({"status": "ok", "reference_id": "ESC-12345678"}),
        )
    )
    await tracker.finalize()

    assert len(calls) == 1
    row = calls[0]
    assert row["call_id"] == "room-e"
    assert row["outcome"] == OUTCOME_SUCCESS
    assert row["success_type"] == SUCCESS_TYPE_ESCALATION
    assert row["escalated_ref"] == "ESC-12345678"
    assert row["failure_reason"] is None
    assert row["ended_at"] is not None
    assert row["duration_seconds"] >= 0


@pytest.mark.asyncio
async def test_flow_conversational_guidance_success(monkeypatch):
    calls = []

    async def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(analytics_module, "finalize_call_analytics", fake_finalize)

    tracker = CallAnalyticsTracker(call_id="room-g", channel="browser")
    tracker._on_conversation_item_added(
        _user_message("My stomach has been hurting since last night.")
    )
    tracker._on_conversation_item_added(
        _assistant_message(
            "I am sorry to hear that. For a mild stomach ache, rest and sip water."
        )
    )
    await tracker.finalize()

    assert len(calls) == 1
    assert calls[0]["outcome"] == OUTCOME_SUCCESS
    assert calls[0]["success_type"] == SUCCESS_TYPE_GUIDANCE
    assert calls[0]["escalated_ref"] is None


@pytest.mark.asyncio
async def test_flow_failed_no_success_condition(monkeypatch):
    calls = []

    async def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(analytics_module, "finalize_call_analytics", fake_finalize)

    tracker = CallAnalyticsTracker(call_id="room-f", channel="browser")
    tracker._on_conversation_item_added(_user_message("Hi"))
    tracker._on_conversation_item_added(_assistant_message("Hello!"))
    await tracker.finalize()

    assert len(calls) == 1
    assert calls[0]["outcome"] == OUTCOME_FAILED
    assert calls[0]["failure_reason"] == FAILURE_REASON_NO_SUCCESS


@pytest.mark.asyncio
async def test_flow_error_close_is_failed(monkeypatch):
    calls = []

    async def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(analytics_module, "finalize_call_analytics", fake_finalize)

    tracker = CallAnalyticsTracker(call_id="room-err", channel="sip")
    await tracker.finalize(close_reason=CloseReason.ERROR.value)

    assert len(calls) == 1
    assert calls[0]["outcome"] == OUTCOME_FAILED
    assert calls[0]["failure_reason"] == FAILURE_REASON_ERROR


@pytest.mark.asyncio
async def test_record_start_passes_metadata(monkeypatch):
    captured = {}

    async def fake_start(call_id, user_id, channel, language):
        captured.update(
            call_id=call_id, user_id=user_id, channel=channel, language=language
        )
        return True

    monkeypatch.setattr(analytics_module, "start_call_analytics", fake_start)

    tracker = CallAnalyticsTracker(
        call_id="room-s", user_id="saathi_abc", channel="sip", language="Hindi"
    )
    await tracker.record_start()

    assert captured == {
        "call_id": "room-s",
        "user_id": "saathi_abc",
        "channel": "sip",
        "language": "Hindi",
    }


def test_invalid_channel_falls_back_to_browser():
    tracker = CallAnalyticsTracker(call_id="room-c", channel="webrtc")
    assert tracker.channel == "browser"


# ---------------------------------------------------------------------------
# 5. Fail-soft: database failures never raise
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fail_soft_when_db_down(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(analytics_module, "start_call_analytics", boom)
    monkeypatch.setattr(analytics_module, "finalize_call_analytics", boom)

    tracker = CallAnalyticsTracker(call_id="room-fs", channel="browser")
    await tracker.record_start()  # must not raise
    tracker._on_conversation_item_added(
        _user_message("I have had a fever since yesterday.")
    )
    tracker._on_conversation_item_added(
        _assistant_message("For a mild fever, please rest and drink plenty of fluids.")
    )
    await tracker.finalize()  # must not raise

    assert tracker.guidance_marker == "conversation"
    assert tracker.finalized is True


@pytest.mark.asyncio
async def test_db_helpers_fail_soft(monkeypatch):
    """The db.py helpers themselves must swallow errors and return False/None."""

    async def broken_pool():
        return None

    monkeypatch.setattr("db.get_db_pool", broken_pool)

    assert await start_call_analytics(call_id="room-1") is False
    assert (
        await finalize_call_analytics(call_id="room-1", outcome=OUTCOME_SUCCESS)
        is False
    )
    assert await get_call_analytics_summary() is None


# ---------------------------------------------------------------------------
# 6. Idempotent finalize
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finalize_is_idempotent(monkeypatch):
    calls = []

    async def fake_finalize(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(analytics_module, "finalize_call_analytics", fake_finalize)

    tracker = CallAnalyticsTracker(call_id="room-i", channel="browser")
    await tracker.finalize()
    await tracker.finalize()
    await tracker.finalize()

    assert len(calls) == 1, "finalize must persist exactly once"


# ---------------------------------------------------------------------------
# 7. Privacy: no sensitive fields on the analytics surface
# ---------------------------------------------------------------------------


def test_tracker_surface_has_no_sensitive_fields():
    import inspect

    init_params = set(inspect.signature(CallAnalyticsTracker.__init__).parameters)
    assert init_params.isdisjoint(FORBIDDEN_FIELDS)

    start_params = set(inspect.signature(start_call_analytics).parameters)
    assert start_params.isdisjoint(FORBIDDEN_FIELDS)

    finalize_params = set(inspect.signature(finalize_call_analytics).parameters)
    assert finalize_params.isdisjoint(FORBIDDEN_FIELDS)


def test_call_analytics_table_columns_are_metadata_only():
    """The call_analytics DDL in db.py must contain ONLY allowed metadata columns."""
    src = (Path(__file__).resolve().parent.parent / "src" / "db.py").read_text(
        encoding="utf-8"
    )
    start = src.index("CREATE TABLE IF NOT EXISTS call_analytics")
    end = src.index(");", start)
    ddl = src[start:end]

    allowed = {
        "id",
        "call_id",
        "user_id",
        "channel",
        "started_at",
        "ended_at",
        "duration_seconds",
        "outcome",
        "success_type",
        "failure_reason",
        "escalated_ref",
        "language",
    }
    columns = re.findall(
        r"^\s*([a-z_]+)\s+(?:SERIAL|VARCHAR|TIMESTAMP|INTEGER|BOOLEAN|TEXT|JSONB)",
        ddl,
        re.IGNORECASE | re.MULTILINE,
    )
    assert columns, "no columns extracted from call_analytics DDL"
    assert set(columns) == allowed, f"unexpected analytics columns: {set(columns)}"


# ---------------------------------------------------------------------------
# 8. Live DB roundtrip (skips if PostgreSQL unreachable)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_live_db_roundtrip_and_summary() -> None:
    """Real start -> finalize -> summary roundtrip against PostgreSQL."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip(
            "PostgreSQL is not reachable (DATABASE_URL) — cannot verify analytics table"
        )

    call_id = f"room-analytics-test-{uuid.uuid4().hex[:8]}"
    user_id = f"saathi_analytics_{random.randint(1000, 9999)}"

    ok = await start_call_analytics(
        call_id=call_id, user_id=user_id, channel="browser", language="Hindi"
    )
    assert ok is True

    # Duplicate start is idempotent — still exactly one row.
    ok_dup = await start_call_analytics(
        call_id=call_id, user_id=user_id, channel="browser", language="Hindi"
    )
    assert ok_dup is True

    try:
        summary = await get_call_analytics_summary()
        assert summary is not None
        assert summary["total"] >= 1
        before_success = summary["successful"]

        ok = await finalize_call_analytics(
            call_id=call_id,
            outcome=OUTCOME_SUCCESS,
            success_type=SUCCESS_TYPE_GUIDANCE,
            failure_reason=None,
            escalated_ref=None,
            ended_at=datetime.now(timezone.utc),
            duration_seconds=42,
        )
        assert ok is True

        # Second finalize (different outcome) must be a no-op — idempotent.
        ok2 = await finalize_call_analytics(
            call_id=call_id,
            outcome=OUTCOME_FAILED,
            failure_reason=FAILURE_REASON_NO_SUCCESS,
        )
        assert ok2 is True

        summary2 = await get_call_analytics_summary()
        assert summary2["successful"] == before_success + 1

        # Channel filter only counts browser rows in this test run.
        browser_summary = await get_call_analytics_summary(channel="browser")
        assert browser_summary["successful"] >= before_success + 1

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM call_analytics WHERE call_id = $1", call_id
            )
        assert row is not None
        assert row["outcome"] == OUTCOME_SUCCESS  # first finalize wins
        assert row["success_type"] == SUCCESS_TYPE_GUIDANCE
        assert row["failure_reason"] is None
        assert row["channel"] == "browser"
        assert row["language"] == "Hindi"
        assert row["user_id"] == user_id
        assert row["duration_seconds"] == 42
        assert row["ended_at"] is not None
        assert row["started_at"] is not None
    finally:
        # Remove ONLY the rows this test created — never touches real data.
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM call_analytics WHERE call_id = $1", call_id)


# ---------------------------------------------------------------------------
# 9. Integration-style flows: real AgentSession events + real PostgreSQL.
#    No LLM is used — these exercise the deterministic analytics wiring exactly
#    as the agent jobs will (start -> wire -> events -> close -> finalize).
# ---------------------------------------------------------------------------


def _emit_close(session, reason=CloseReason.PARTICIPANT_DISCONNECTED):
    session.emit("close", CloseEvent(reason=reason))


@pytest.mark.asyncio
async def test_live_session_guidance_call_flow() -> None:
    """A guidance call through a real AgentSession finalizes success/guidance."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip("PostgreSQL is not reachable — cannot verify live flow")

    call_id = f"room-flow-guidance-{uuid.uuid4().hex[:8]}"
    session = AgentSession()
    tracker = CallAnalyticsTracker(
        call_id=call_id, user_id="saathi_flow_test", channel="browser"
    )
    await tracker.record_start()
    tracker.wire(session)

    session.emit(
        "conversation_item_added",
        _user_message("I have had a mild fever and headache since yesterday."),
    )
    session.emit(
        "conversation_item_added",
        _assistant_message(
            "Thank you for telling me. For a mild fever, please rest and drink plenty of fluids."
        ),
    )
    _emit_close(session)
    await tracker.finalize()  # idempotent — the close handler also awaits it

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM call_analytics WHERE call_id = $1", call_id
            )
        assert row is not None
        assert row["outcome"] == OUTCOME_SUCCESS
        assert row["success_type"] == SUCCESS_TYPE_GUIDANCE
        assert row["channel"] == "browser"
        assert row["user_id"] == "saathi_flow_test"
        assert row["ended_at"] is not None
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM call_analytics WHERE call_id = $1", call_id)


@pytest.mark.asyncio
async def test_live_session_escalation_call_flow() -> None:
    """An escalation call through a real AgentSession finalizes success/escalation."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip("PostgreSQL is not reachable — cannot verify live flow")

    call_id = f"room-flow-escalation-{uuid.uuid4().hex[:8]}"
    session = AgentSession()
    tracker = CallAnalyticsTracker(
        call_id=call_id, user_id="saathi_flow_test", channel="browser"
    )
    await tracker.record_start()
    tracker.wire(session)

    session.emit(
        "function_tools_executed",
        _tool_event(
            "create_escalation",
            json.dumps({"status": "ok", "reference_id": "ESC-FLOW1234"}),
        ),
    )
    _emit_close(session)
    await tracker.finalize()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM call_analytics WHERE call_id = $1", call_id
            )
        assert row is not None
        assert row["outcome"] == OUTCOME_SUCCESS
        assert row["success_type"] == SUCCESS_TYPE_ESCALATION
        assert row["escalated_ref"] == "ESC-FLOW1234"
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM call_analytics WHERE call_id = $1", call_id)


@pytest.mark.asyncio
async def test_live_session_greeting_only_failed() -> None:
    """A call that ends after only the greeting finalizes failed (no_response)."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip("PostgreSQL is not reachable — cannot verify live flow")

    call_id = f"room-flow-greeting-{uuid.uuid4().hex[:8]}"
    session = AgentSession()
    tracker = CallAnalyticsTracker(call_id=call_id, channel="browser")
    await tracker.record_start()
    tracker.wire(session)

    session.emit(
        "conversation_item_added",
        _assistant_message(
            "Namaste! I am Saathi, your health assistant. How are you feeling today?"
        ),
    )
    _emit_close(session)
    await tracker.finalize()

    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM call_analytics WHERE call_id = $1", call_id
            )
        assert row is not None
        assert row["outcome"] == OUTCOME_FAILED
        assert row["failure_reason"] == FAILURE_REASON_NO_RESPONSE
        assert row["success_type"] is None
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM call_analytics WHERE call_id = $1", call_id)


@pytest.mark.asyncio
async def test_live_duplicate_finalize_persists_one_record() -> None:
    """Duplicate finalization never double-counts: one row, first outcome wins."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip("PostgreSQL is not reachable — cannot verify live flow")

    call_id = f"room-flow-dup-{uuid.uuid4().hex[:8]}"
    session = AgentSession()
    tracker = CallAnalyticsTracker(call_id=call_id, channel="sip")
    await tracker.record_start()
    tracker.wire(session)

    session.emit(
        "function_tools_executed",
        _tool_event("analyze_symptoms", "LOW/MODERATE: rest and monitor symptoms."),
    )
    _emit_close(session)
    await tracker.finalize()
    await tracker.finalize(close_reason=CloseReason.ERROR.value)

    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM call_analytics WHERE call_id = $1", call_id
            )
        assert len(rows) == 1, "duplicate finalize must never create a second row"
        row = rows[0]
        assert row["outcome"] == OUTCOME_SUCCESS
        assert row["success_type"] == SUCCESS_TYPE_GUIDANCE
    finally:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM call_analytics WHERE call_id = $1", call_id)


@pytest.mark.asyncio
async def test_live_session_db_down_call_unaffected(monkeypatch) -> None:
    """With PostgreSQL unavailable the session flow still completes without raising."""

    async def boom(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr(analytics_module, "start_call_analytics", boom)
    monkeypatch.setattr(analytics_module, "finalize_call_analytics", boom)

    session = AgentSession()
    tracker = CallAnalyticsTracker(call_id="room-flow-dbdown", channel="browser")
    await tracker.record_start()  # must not raise
    tracker.wire(session)

    session.emit(
        "conversation_item_added",
        _user_message("I have had a fever since yesterday."),
    )
    session.emit(
        "conversation_item_added",
        _assistant_message("For a mild fever, please rest and drink plenty of fluids."),
    )
    _emit_close(session)
    await tracker.finalize()  # must not raise

    assert tracker.guidance_marker == "conversation"
    assert tracker.finalized is True
