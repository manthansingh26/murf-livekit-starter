import pytest
from livekit.agents import AgentSession, inference, llm
from livekit.plugins import google
from agent import Assistant

def _judge_llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")

def _agent_llm() -> llm.LLM:
    return google.LLM(model="gemini-3.5-flash-lite")

async def _get_agent_response_assert(result):
    while True:
        event_assert = result.expect.next_event()
        try:
            chat_message_assert = event_assert.is_message(role="assistant")
            return chat_message_assert
        except Exception:
            pass

@pytest.mark.asyncio
async def test_1_gujarati() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="મને બે દિવસથી તાવ છે.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(
            judge,
            intent="The agent MUST respond in natural Gujarati script. The response MUST NOT be in Hindi or English."
        )

@pytest.mark.asyncio
async def test_2_hindi() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="मुझे दो दिन से बुखार है।")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(
            judge,
            intent="The agent MUST respond in natural Hindi (Devanagari script). The response MUST NOT be in Gujarati or English."
        )

@pytest.mark.asyncio
async def test_3_english() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="I have had a fever for two days.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(
            judge,
            intent="The agent MUST respond in natural English. The response MUST NOT be in Hindi or Gujarati."
        )

@pytest.mark.asyncio
async def test_4_english_to_gujarati() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        
        # Turn 1: English
        result = await session.run(user_input="I have been feeling weak since yesterday.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="Respond in English.")
        
        # Turn 2: Switch to Gujarati
        result = await session.run(user_input="હવે મને માથું પણ દુખે છે.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="The agent MUST immediately switch to Gujarati script. It MUST NOT say 'I will speak Gujarati now' or announce the switch. It MUST NOT speak Hindi.")

@pytest.mark.asyncio
async def test_5_gujarati_to_english() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="મને પેટમાં દુખાવો થાય છે.")
        await _get_agent_response_assert(result)
        
        result = await session.run(user_input="And I also feel nauseous.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="The agent MUST immediately switch to English. It MUST NOT announce the switch.")

@pytest.mark.asyncio
async def test_6_gujarati_to_hindi() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="મને તાવ છે.")
        await _get_agent_response_assert(result)
        
        result = await session.run(user_input="और मुझे खांसी भी है।")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="The agent MUST immediately switch to Hindi (Devanagari script). It MUST NOT announce the switch. It MUST NOT continue in Gujarati.")

@pytest.mark.asyncio
async def test_7_hindi_to_gujarati() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="मुझे सिरदर्द हो रहा है।")
        await _get_agent_response_assert(result)
        
        result = await session.run(user_input="અને મને ચક્કર પણ આવે છે.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="The agent MUST immediately switch to Gujarati script. It MUST NOT announce the switch. It MUST NOT continue in Hindi.")

@pytest.mark.asyncio
async def test_8_code_mixed_gujarati() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="મને fever છે અને body બહુ weak લાગે છે.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(
            judge,
            intent="The agent MUST respond in a natural Gujarati/Hinglish code-mixed register using Gujarati script and English words where appropriate. It MUST NOT respond in pure Hindi."
        )

@pytest.mark.asyncio
async def test_9_code_mixed_hindi() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        result = await session.run(user_input="मुझे थोड़ा fever है और body pain भी है.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(
            judge,
            intent="The agent MUST respond in a natural Hindi/Hinglish code-mixed register using Devanagari script and English words where appropriate. It MUST NOT respond in pure Gujarati."
        )

@pytest.mark.asyncio
async def test_10_rapid_switching() -> None:
    async with _judge_llm() as judge, _agent_llm() as agent_llm, AgentSession(llm=agent_llm) as session:
        await session.start(Assistant())
        
        # English
        result = await session.run(user_input="I have a headache.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="Respond in English.")
        
        # Gujarati
        result = await session.run(user_input="અને મને ચક્કર પણ આવે છે.")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="Respond in Gujarati script.")
        
        # Hindi
        result = await session.run(user_input="और मुझे खांसी भी है।")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="Respond in Hindi Devanagari script.")
        
        # English
        result = await session.run(user_input="Do you think I need medicine?")
        msg_assert = await _get_agent_response_assert(result)
        await msg_assert.judge(judge, intent="Respond in English. Must refuse prescription.")
