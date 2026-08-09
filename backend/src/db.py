import os
import logging
import json
import asyncpg
from datetime import datetime

logger = logging.getLogger("db")

db_pool: asyncpg.Pool = None

async def init_db():
    global db_pool
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable is not set.")
        return

    try:
        db_pool = await asyncpg.create_pool(db_url, server_settings={'client_encoding': 'UTF8'})
        
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
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

async def get_db_pool() -> asyncpg.Pool:
    global db_pool
    if db_pool is None:
        await init_db()
    return db_pool

async def lookup_caller(user_id: str):
    pool = await get_db_pool()
    if not pool:
        return None
    
    async with pool.acquire() as conn:
        record = await conn.fetchrow("""
            SELECT user_id, name, language_preference, facts, last_interaction 
            FROM caller_memory 
            WHERE user_id = $1
        """, user_id)
        
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
        await conn.execute("""
            INSERT INTO caller_memory (user_id, name, language_preference, facts, last_interaction)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id) DO UPDATE 
            SET name = EXCLUDED.name,
                language_preference = EXCLUDED.language_preference,
                facts = EXCLUDED.facts,
                last_interaction = EXCLUDED.last_interaction;
        """, user_id, name, language_preference, facts_json, now)
    return True
