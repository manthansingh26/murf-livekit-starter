import asyncio
import json
import logging
import os
from datetime import datetime

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
