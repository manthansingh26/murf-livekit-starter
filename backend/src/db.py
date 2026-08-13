import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Optional

import asyncpg

logger = logging.getLogger("db")

db_pool: asyncpg.Pool = None


def db_target_info() -> tuple[str, str, str]:
    """Return (host, port, database) parsed from DATABASE_URL, WITHOUT any password.

    Used only for diagnostics — never logs credentials.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        return "unset", "unset", "unset"
    try:
        # Drop any userinfo (user:password@) prefix — we never want to log it.
        rest = url.split("@")[-1]
        host_port, _, db = rest.partition("/")
        if ":" in host_port:
            host, port = host_port.rsplit(":", 1)
        else:
            host, port = host_port, "5432"
        return host or "localhost", port, db or "postgres"
    except Exception:
        return "unknown", "unknown", "unknown"


async def init_db():
    global db_pool
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set.")
        return

    try:
        db_pool = await asyncpg.create_pool(
            db_url, server_settings={"client_encoding": "UTF8"}
        )

        async with db_pool.acquire() as conn:
            await conn.execute("SET client_encoding = 'UTF8';")
            # Create schema if it doesn't exist
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS caller_memory (
                    user_id VARCHAR(255) PRIMARY KEY,
                    name VARCHAR(255),
                    language_preference VARCHAR(50),
                    facts JSONB DEFAULT '{}'::jsonb,
                    last_interaction TIMESTAMP WITH TIME ZONE
                );
            """)
            # Day 7 Phase 2 — human escalation foundation. Only the short
            # human-help summary is stored here; NEVER sensitive credentials
            # (passwords, OTPs, PINs, account numbers) or full transcripts.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS escalation_requests (
                    id SERIAL PRIMARY KEY,
                    reference_id VARCHAR(32) UNIQUE NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    reason VARCHAR(32) NOT NULL,
                    what_happened TEXT NOT NULL,
                    agent_action TEXT,
                    urgency VARCHAR(16) NOT NULL,
                    language VARCHAR(32),
                    preferred_follow_up VARCHAR(64),
                    consent_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR(16) NOT NULL DEFAULT 'OPEN',
                    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
                );
            """)
            # Day 8 — call analytics. Stores ONLY minimum metadata so the
            # dashboard can show real call counts: opaque caller id, channel,
            # timestamps, duration, and a deterministic outcome. NEVER stores
            # transcripts, medical details, summaries, or credentials.
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS call_analytics (
                    id SERIAL PRIMARY KEY,
                    call_id VARCHAR(64) UNIQUE NOT NULL,
                    user_id VARCHAR(255),
                    channel VARCHAR(16) NOT NULL,
                    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                    ended_at TIMESTAMP WITH TIME ZONE,
                    duration_seconds INTEGER,
                    outcome VARCHAR(16),
                    success_type VARCHAR(16),
                    failure_reason VARCHAR(32),
                    escalated_ref VARCHAR(32),
                    language VARCHAR(16)
                );
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_call_analytics_outcome
                ON call_analytics (outcome);
            """)
        host, port, db_name = db_target_info()
        logger.info(
            f"[MEMORY DEBUG] db_host={host} db_port={port} db_name={db_name} connection=OK"
        )
    except Exception as e:
        host, port, db_name = db_target_info()
        logger.error(
            f"[MEMORY DEBUG] db_host={host} db_port={port} db_name={db_name} "
            f"connection=FAILED reason={type(e).__name__}: {e}"
        )


async def get_db_pool() -> asyncpg.Pool:
    global db_pool
    try:
        cur_loop = asyncio.get_running_loop()
    except RuntimeError:
        cur_loop = None

    if db_pool is not None:
        is_closed = getattr(db_pool, "_closed", False)
        pool_loop = getattr(db_pool, "_loop", None)
        if is_closed or (cur_loop and pool_loop is not cur_loop):
            db_pool = None

    if db_pool is None:
        await init_db()
    return db_pool


async def lookup_caller(user_id: str):
    pool = await get_db_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            SELECT user_id, name, language_preference, facts, last_interaction
            FROM caller_memory
            WHERE user_id = $1
        """,
            user_id,
        )

        if record:
            return dict(record)
        return None


async def save_caller(user_id: str, name: str, language_preference: str, facts: dict):
    pool = await get_db_pool()
    if not pool:
        return False

    facts_json = json.dumps(facts)
    now = datetime.now()

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO caller_memory (user_id, name, language_preference, facts, last_interaction)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE
            SET name = EXCLUDED.name,
                language_preference = EXCLUDED.language_preference,
                facts = EXCLUDED.facts,
                last_interaction = EXCLUDED.last_interaction;
        """,
            user_id,
            name,
            language_preference,
            facts_json,
            now,
        )
    logger.info(f"[MEMORY DEBUG] save_result=OK user_id={user_id}")
    return True


async def save_escalation(
    reference_id: str,
    user_id: str,
    reason: str,
    what_happened: str,
    agent_action: Optional[str] = None,
    urgency: str = "medium",
    language: Optional[str] = None,
    preferred_follow_up: Optional[str] = None,
    consent_confirmed: bool = False,
    status: str = "OPEN",
):
    """Persist a human-help escalation request (Day 7 Phase 2).

    reason: "red_flag_symptom" | "diagnosis_request"
    urgency: "low" | "medium" | "high" | "emergency"
    status: "OPEN" | "IN_PROGRESS" | "RESOLVED"

    The reference_id is generated by the caller (Phase 3 escalation tool) and
    must be unique. Returns the created row as a dict, or None when the
    database is unreachable. NEVER pass credentials or full transcripts here.
    """
    pool = await get_db_pool()
    if not pool:
        return None

    async with pool.acquire() as conn:
        record = await conn.fetchrow(
            """
            INSERT INTO escalation_requests (
                reference_id,
                user_id,
                reason,
                what_happened,
                agent_action,
                urgency,
                language,
                preferred_follow_up,
                consent_confirmed,
                status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id, reference_id, user_id, reason, what_happened,
                      agent_action, urgency, language, preferred_follow_up,
                      consent_confirmed, status, created_at, updated_at
            """,
            reference_id,
            user_id,
            reason,
            what_happened,
            agent_action,
            urgency,
            language,
            preferred_follow_up,
            consent_confirmed,
            status,
        )
        if record:
            return dict(record)
        return None


async def list_open_escalations():
    """Return all escalation requests with status 'OPEN', oldest first.

    Returns an empty list when the database is unreachable.
    """
    pool = await get_db_pool()
    if not pool:
        return []

    async with pool.acquire() as conn:
        records = await conn.fetch(
            """
            SELECT id, reference_id, user_id, reason, what_happened,
                   agent_action, urgency, language, preferred_follow_up,
                   consent_confirmed, status, created_at, updated_at
            FROM escalation_requests
            WHERE status = 'OPEN'
            ORDER BY created_at ASC
            """
        )
        return [dict(r) for r in records]


async def start_call_analytics(
    call_id: str,
    user_id: str = "",
    channel: str = "browser",
    language: Optional[str] = None,
) -> bool:
    """Record the start of a call in the analytics table (Day 8).

    Idempotent per call_id (the room name is unique per call for both the
    browser and the outbound SIP agents), so a duplicate insert never creates
    a second row. Fail-soft: returns False and logs instead of raising, so
    analytics can never break a live voice call.

    channel: 'browser' | 'sip'
    """
    pool = await get_db_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO call_analytics (call_id, user_id, channel, language)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (call_id) DO NOTHING
                """,
                call_id,
                (user_id or "").strip()[:255] or None,
                (channel or "browser").strip()[:16],
                (language or "").strip()[:16] or None,
            )
        return True
    except Exception as e:
        logger.error(
            f"[ANALYTICS] start_call_analytics failed call_id={call_id} reason={e}"
        )
        return False


async def finalize_call_analytics(
    call_id: str,
    outcome: str,
    success_type: Optional[str] = None,
    failure_reason: Optional[str] = None,
    escalated_ref: Optional[str] = None,
    ended_at: Optional[datetime] = None,
    duration_seconds: Optional[int] = None,
) -> bool:
    """Finalize one call's outcome (Day 8).

    Idempotent: only rows whose outcome is still NULL are updated, so a second
    finalization can never overwrite or double-count a call. Fail-soft like
    start_call_analytics.
    """
    pool = await get_db_pool()
    if not pool:
        return False

    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE call_analytics
                SET outcome = $2,
                    success_type = $3,
                    failure_reason = $4,
                    escalated_ref = $5,
                    ended_at = $6,
                    duration_seconds = $7
                WHERE call_id = $1 AND outcome IS NULL
                """,
                call_id,
                (outcome or "").strip()[:16],
                (success_type or "").strip()[:16] or None,
                (failure_reason or "").strip()[:32] or None,
                (escalated_ref or "").strip()[:32] or None,
                ended_at,
                duration_seconds,
            )
        return True
    except Exception as e:
        logger.error(
            f"[ANALYTICS] finalize_call_analytics failed call_id={call_id} reason={e}"
        )
        return False


async def get_call_analytics_summary(channel: Optional[str] = None):
    """Aggregate analytics counts for the dashboard (Day 8).

    Returns a dict {total, successful, failed, success_rate, last_updated}
    computed from REAL call_analytics rows, or None when the database is
    unreachable. `total` includes in-flight calls (outcome IS NULL) — they
    count as calls but are not yet successful or failed.
    """
    pool = await get_db_pool()
    if not pool:
        return None

    try:
        async with pool.acquire() as conn:
            if channel:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE outcome = 'success') AS successful,
                           COUNT(*) FILTER (WHERE outcome = 'failed') AS failed,
                           MAX(ended_at) AS last_updated
                    FROM call_analytics
                    WHERE channel = $1
                    """,
                    (channel or "").strip()[:16],
                )
            else:
                row = await conn.fetchrow(
                    """
                    SELECT COUNT(*) AS total,
                           COUNT(*) FILTER (WHERE outcome = 'success') AS successful,
                           COUNT(*) FILTER (WHERE outcome = 'failed') AS failed,
                           MAX(ended_at) AS last_updated
                    FROM call_analytics
                    """
                )
        if row is None:
            return None
        total = row["total"]
        successful = row["successful"]
        failed = row["failed"]
        success_rate = round(100.0 * successful / total, 1) if total else 0.0
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": success_rate,
            "last_updated": row["last_updated"],
        }
    except Exception as e:
        logger.error(f"[ANALYTICS] get_call_analytics_summary failed reason={e}")
        return None
