"""Day 4 regression tests — Call 1 -> consent -> save -> Call 2 -> lookup -> recognize.

These tests do NOT replace existing tests; they add coverage for the identity and
persistence flow that was broken (a new random caller ID per call + an unreachable
DATABASE_URL meant Call 2 could never find Call 1's record).
"""

import random

import pytest

from agent import (
    Assistant,
    analyze_consent_turn,
    detect_language,
    format_returning_caller_instruction,
)
from db import db_target_info, get_db_pool, init_db, lookup_caller, save_caller

# ---------------------------------------------------------------------------
# 1. Stable caller ID
# ---------------------------------------------------------------------------


def test_assistant_stores_stable_caller_id() -> None:
    caller_id = "saathi_stable_uuid_123"
    agent = Assistant(user_id=caller_id)
    assert agent.user_id == caller_id
    # The system prompt must be formatted with the caller's ID so the memory
    # tools are told which user_id to use.
    assert caller_id in agent._instructions


def test_returning_caller_instruction_uses_database_record() -> None:
    record = {
        "user_id": "saathi_abc",
        "name": "Manthan",
        "language_preference": "English",
        "facts": {"age_band": "18 to 25"},
        "last_interaction": "2026-08-10 10:00:00+00:00",
    }
    instr = format_returning_caller_instruction(record)
    assert "Manthan" in instr
    assert "age_band" in instr
    assert "RETURNING CALLER" in instr
    assert "DO NOT ask" in instr


def test_returning_caller_instruction_handles_string_facts() -> None:
    instr = format_returning_caller_instruction(
        {
            "name": "Manthan",
            "language_preference": "Hindi",
            "facts": '{"age_band": "60+"}',
        }
    )
    assert "Manthan" in instr
    assert "60+" in instr


# ---------------------------------------------------------------------------
# 2 / 8 / 9. Consent required / rejected / granted
# ---------------------------------------------------------------------------


def test_consent_required_when_info_shared() -> None:
    assert (
        analyze_consent_turn("Hi, my name is Manthan.") == "PROACTIVE_CONSENT_REQUIRED"
    )


def test_explicit_save_request() -> None:
    # personal info + an explicit save word -> agent may save immediately
    assert (
        analyze_consent_turn("Please remember my name is Manthan.")
        == "EXPLICIT_SAVE_REQUESTED"
    )


def test_yes_remember_is_consent_granted() -> None:
    # pure affirmation of a prior consent question -> granted
    assert analyze_consent_turn("Yes, remember my name please.") == "CONSENT_GRANTED"


def test_consent_granted() -> None:
    assert analyze_consent_turn("Yes, you can save it.") == "CONSENT_GRANTED"


def test_consent_rejected() -> None:
    assert analyze_consent_turn("No, don't save that.") == "CONSENT_REJECTED"


def test_consent_rejected_hindi() -> None:
    assert analyze_consent_turn("नहीं, सेव मत करो।") == "CONSENT_REJECTED"


def test_consent_granted_hindi() -> None:
    assert analyze_consent_turn("हाँ, याद रखो।") == "CONSENT_GRANTED"


def test_normal_turn_no_consent_action() -> None:
    assert analyze_consent_turn("I have had a fever for two days.") == "NORMAL_TURN"


# ---------------------------------------------------------------------------
# 11. Multilingual regression (pure detection; the full LLM language-switching
#     suite lives in tests/test_multilingual.py)
# ---------------------------------------------------------------------------


def test_language_english() -> None:
    assert detect_language("I have had a fever for two days.") == "English"


def test_language_hindi() -> None:
    assert detect_language("मुझे दो दिन से बुखार है।") == "Hindi"


def test_language_gujarati() -> None:
    assert detect_language("મને બે દિવસથી તાવ છે.") == "Gujarati"


def test_language_code_mixed_gujarati() -> None:
    assert detect_language("મને fever છે અને body બહુ weak લાગે છે.") == "Gujarati"


def test_language_code_mixed_hindi_falls_back_to_english_heuristic() -> None:
    # Pre-existing detector heuristic: latin words trigger English before Devanagari
    # is considered. The full agent-level code-mixed coverage lives in
    # tests/test_multilingual.py (LLM-judged); this documents the heuristic.
    assert detect_language("मुझे थोड़ा fever है और body pain भी है।") == "English"


# ---------------------------------------------------------------------------
# 12. Database connection configuration
# ---------------------------------------------------------------------------


def test_db_target_info_never_leaks_password() -> None:
    host, port, db = db_target_info()
    assert host and port and db
    assert "@" not in host  # never contains userinfo
    assert ":" not in host  # never contains a password


@pytest.mark.asyncio
async def test_call1_save_call2_lookup_same_caller_id() -> None:
    """Proves: Call 1 saves -> Call 2 (same caller ID) finds the record in PostgreSQL.

    A different caller ID must NOT see the record. Skips when PostgreSQL is unreachable
    so the suite still runs in CI without a database.
    """
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip(
            "PostgreSQL is not reachable (DATABASE_URL) — cannot verify persistence"
        )

    caller_id = f"saathi_test_{random.randint(1000, 9999)}"

    # CALL 1: explicit save (as the agent would after consent)
    ok = await save_caller(
        user_id=caller_id,
        name="Manthan",
        language_preference="English",
        facts={"age_band": "18 to 25"},
    )
    assert ok is True

    try:
        # CALL 2: lookup with the SAME stable caller ID
        record = await lookup_caller(caller_id)
        assert record is not None
        assert record["user_id"] == caller_id
        assert record["name"] == "Manthan"
        assert record["language_preference"] == "English"

        # A different caller ID must NOT find this record
        assert await lookup_caller(f"other_{caller_id}") is None
    finally:
        # Remove ONLY the row this test created — never touches real caller data.
        # (Use the pool object returned by get_db_pool(); the module-level `db_pool`
        # name imported at module load can be stale before the first init_db().)
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM caller_memory WHERE user_id = $1", caller_id
            )
