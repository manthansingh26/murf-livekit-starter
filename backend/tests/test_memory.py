import pytest
from livekit.agents import AgentSession, inference, llm
from agent import Assistant
from db import init_db

from livekit.plugins import google

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
        result = await session.run(
            user_input="Hi Saathi, I am Ramesh. I am in the 18 to 25 age group. Please remember this."
        )
        
        # We expect the agent to ask for consent first!
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm_client,
                intent="The agent MUST explicitly ask for consent before saving the fact about the user's age group."
            )
        )
        
        # Now the user says YES
        result = await session.run(user_input="Yes, you have my permission to save that.")
        
        # We expect the tool call to save memory
        event = result.expect.next_event()
        assert event.is_tool_call()
        assert event.tool_call.function.name == "save_caller_memory"
        
        # Let's inspect the arguments passed to the tool
        args = event.tool_call.function.arguments
        assert args["user_id"] == caller_id
        assert "Ramesh" in args["name"]
        
        # Acknowledge the tool call
        result.expect.no_more_events()
        
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
        
        # Expect the agent to call the lookup tool
        event = result.expect.next_event()
        if event.is_tool_call():
            assert event.tool_call.function.name == "lookup_caller_memory"
            
            # Now we expect the agent to greet Ramesh!
            await (
                result.expect.next_event()
                .is_message(role="assistant")
                .judge(
                    llm_client,
                    intent="The agent MUST recognize the returning caller and greet Ramesh by name."
                )
            )
        else:
            # Maybe it already looked it up or just responds directly with the greeting if it knows it from the system prompt
            # But we instructed it to use the tool. If it didn't use the tool, it should still greet Ramesh.
            await (
                event.is_message(role="assistant")
                .judge(
                    llm_client,
                    intent="The agent MUST recognize the returning caller and greet Ramesh by name."
                )
            )
