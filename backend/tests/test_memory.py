import json

import pytest
from livekit.agents import AgentSession
from livekit.plugins import google

from agent import Assistant
from db import init_db


def _llm():
    return google.LLM(model="gemini-3.5-flash-lite")


@pytest.mark.asyncio
async def test_memory_across_calls() -> None:
    """Evaluation of the agent's ability to save and retrieve memory across calls."""
    await init_db()

    import random

    caller_id = f"test_memory_user_{random.randint(1000, 9999)}"

    # CALL 1
    async with (
        _llm() as llm_client,
        AgentSession(llm=llm_client) as session,
    ):
        agent = Assistant(user_id=caller_id)
        await session.start(agent)

        # 1. User provides name and a useful fact
        # 2. Agent asks permission
        # 3. Caller says YES
        # 4. PostgreSQL record is created

        # In a test, we can directly invoke the tool to simulate the LLM choosing to call it,
        # or we can test if the LLM calls the tool when prompted.
        # NOTE: plain personal info (no explicit "save/remember" request) MUST trigger a
        # consent ask — this is the Day 4 proactive-consent contract. An explicit
        # "please remember this" would legitimately allow an immediate save instead.
        result = await session.run(
            user_input="Hi Saathi, I am Ramesh. I am in the 18 to 25 age group."
        )

        # We expect the agent to ask for consent first!
        # (Skip past any tool calls, e.g. the prompt-driven lookup_caller_memory.)
        chat_message_assert = None
        for _ in range(50):
            try:
                chat_message_assert = result.expect.next_event().is_message(
                    role="assistant"
                )
                break
            except Exception:
                continue
        assert chat_message_assert is not None, "agent never produced a message"
        await chat_message_assert.judge(
            llm_client,
            intent="The agent MUST explicitly ask for consent before saving the fact about the user's age group.",
        )

        # Now the user says YES
        result = await session.run(
            user_input="Yes, you have my permission to save that."
        )

        # We expect a save_caller_memory tool call (skip any other events)
        saved_args = None
        for _ in range(50):
            ev = result.expect.next_event()
            ev_obj = ev.event()
            name = getattr(getattr(ev_obj, "item", None), "name", None)
            if name == "save_caller_memory":
                ev.is_function_call(name="save_caller_memory")
                saved_args = json.loads(ev_obj.item.arguments)
                break
        assert saved_args is not None, "save_caller_memory was never called"

        # Let's inspect the arguments passed to the tool
        assert saved_args["user_id"] == caller_id
        assert "Ramesh" in saved_args["name"]

    # BACKEND RESTART (Simulated by starting a new session and new Assistant instance)
    print("--- SIMULATING BACKEND RESTART ---")

    # CALL 2
    async with (
        _llm() as llm_client,
        AgentSession(llm=llm_client) as session,
    ):
        agent = Assistant(user_id=caller_id)
        await session.start(agent)

        # The prompt says: "When a call starts, you MUST immediately use the `lookup_caller_memory` tool"
        # However, the AgentSession in testing doesn't simulate the room start perfectly to trigger the agent's first proactive turn without input in some test runners,
        # but let's just send a generic "Hello" to kick it off.
        result = await session.run(user_input="Hello.")

        # Expect the agent to recognize the returning caller and greet Ramesh by name.
        # (The deterministic memory injection guarantees the name is in context even if
        # the LLM does not call the lookup tool.)
        message_assert = None
        for _ in range(50):
            try:
                message_assert = result.expect.next_event().is_message(role="assistant")
                break
            except Exception:
                continue
        assert message_assert is not None, "agent never produced a message"
        await message_assert.judge(
            llm_client,
            intent="The agent MUST recognize the returning caller and greet Ramesh by name.",
        )

    # Clean up ONLY the row this test created — never touches real caller data.
    from db import get_db_pool

    pool = await get_db_pool()
    if pool is not None:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM caller_memory WHERE user_id = $1", caller_id
            )
