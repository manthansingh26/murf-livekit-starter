"""Day 7 Phase 2 — PostgreSQL foundation for human escalation.

Verifies:
  - init_db() creates the escalation_requests table
  - save_escalation() inserts a record with the Day 7 value contract
  - list_open_escalations() retrieves OPEN records
  - caller_memory (Day 4) is untouched and still works

Skips when PostgreSQL is unreachable, matching the existing suite.
"""

import random
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")

from db import (  # noqa: E402
    get_db_pool,
    init_db,
    list_open_escalations,
    lookup_caller,
    save_caller,
    save_escalation,
)

# Allowed value contracts (mirrors the Day 7 spec).
ALLOWED_REASONS = {"red_flag_symptom", "diagnosis_request"}
ALLOWED_URGENCIES = {"low", "medium", "high", "emergency"}
ALLOWED_STATUSES = {"OPEN", "IN_PROGRESS", "RESOLVED"}


@pytest.mark.asyncio
async def test_save_and_list_open_escalation() -> None:
    """save_escalation inserts -> list_open_escalations finds it -> cleanup."""
    await init_db()
    pool = await get_db_pool()
    if pool is None:
        pytest.skip(
            "PostgreSQL is not reachable (DATABASE_URL) — cannot verify escalation table"
        )

    reference_id = f"ESC-TEST-{uuid.uuid4().hex[:10]}"
    user_id = f"saathi_esc_test_{random.randint(1000, 9999)}"

    record = await save_escalation(
        reference_id=reference_id,
        user_id=user_id,
        reason="red_flag_symptom",
        what_happened="Caller reported chest pain lasting more than 15 minutes.",
        agent_action="Advised to call 108 emergency services immediately.",
        urgency="high",
        language="English",
        preferred_follow_up="SMS",
        consent_confirmed=True,
    )
    assert record is not None, "save_escalation returned None (insert failed)"
    assert record["reference_id"] == reference_id
    assert record["user_id"] == user_id
    assert record["reason"] == "red_flag_symptom"
    assert record["what_happened"]
    assert record["agent_action"]
    assert record["urgency"] == "high"
    assert record["language"] == "English"
    assert record["preferred_follow_up"] == "SMS"
    assert record["consent_confirmed"] is True
    assert record["status"] == "OPEN"
    assert record["id"] > 0
    assert record["created_at"] is not None

    # Value contract — the columns only hold Day 7 supported values.
    assert record["reason"] in ALLOWED_REASONS
    assert record["urgency"] in ALLOWED_URGENCIES
    assert record["status"] in ALLOWED_STATUSES

    try:
        # New rows are retrievable via list_open_escalations().
        open_escalations = await list_open_escalations()
        assert any(r["reference_id"] == reference_id for r in open_escalations)

        # Day 4 caller_memory is untouched — save + lookup still work.
        ok = await save_caller(
            user_id=user_id,
            name="Escalation Test User",
            language_preference="English",
            facts={"age_band": "18 to 25"},
        )
        assert ok is True
        found = await lookup_caller(user_id)
        assert found is not None
        assert found["user_id"] == user_id
    finally:
        # Remove ONLY the rows this test created — never touches real data.
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM escalation_requests WHERE reference_id = $1",
                reference_id,
            )
            await conn.execute("DELETE FROM caller_memory WHERE user_id = $1", user_id)
