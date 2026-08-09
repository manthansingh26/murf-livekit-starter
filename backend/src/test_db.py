import asyncio
import os
from dotenv import load_dotenv

load_dotenv(".env.local")

from db import init_db, save_caller, lookup_caller

async def test():
    await init_db()
    
    # Save a test caller
    print("Saving caller...")
    await save_caller(
        user_id="test_user_123",
        name="Test Ramesh",
        language_preference="English",
        facts={"age_band": "18-25", "ongoing_condition": "fever"}
    )
    
    # Lookup
    print("Looking up caller...")
    record = await lookup_caller("test_user_123")
    print(record)

if __name__ == "__main__":
    asyncio.run(test())
