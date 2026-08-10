"""LIVE smoke tests — find_nearby_health_facilities (REAL network + REAL Gemini).

These are NOT part of the default suite: they hit real public OpenStreetMap
endpoints and the live Gemini API. Run explicitly with:

    RUN_LIVE_TESTS=1 uv run pytest tests/test_health_access_live.py -v

LIVE TEST verdicts are printed per test.
"""

import json
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LIVE_TESTS") != "1",
    reason="live smoke tests disabled (set RUN_LIVE_TESTS=1)",
)

from tools.health_access import find_nearby_health_facilities_impl  # noqa: E402


@pytest.mark.asyncio
async def test_live_navsari_smoke():
    """LIVE TEST — real external OpenStreetMap lookup for Navsari."""
    out = json.loads(await find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "ok", f"LIVE TEST: FAIL — {out.get('message')}"
    assert out["count"] >= 1, "LIVE TEST: FAIL — zero facilities returned"
    assert out["retrieved_at"], "LIVE TEST: FAIL — missing retrieved_at"
    for f in out["facilities"]:
        assert f["name"] and f["type"] and f["distance_km"] >= 0
    print("LIVE TEST: PASS")
    print("  resolved:", out["resolved_location"])
    for f in out["facilities"][:3]:
        print(
            f"  - {f['name']} | {f['type']} | {f['distance_km']} km | {f['address'][:40]}"
        )


@pytest.mark.asyncio
async def test_live_missing_location_asks_first():
    """LIVE TEST — no location given: agent must ask, not call the tool with a guess."""
    from livekit.agents import AgentSession
    from livekit.plugins import google

    from agent import Assistant

    async with (
        google.LLM(model="gemini-3.5-flash-lite") as llm_client,
        AgentSession(llm=llm_client) as session,
    ):
        await session.start(Assistant(user_id="saathi_live_day5_noloc"))

        result = await session.run(user_input="Can you find me a nearby health centre?")

        # The agent must ask for a location, NOT call find_nearby_health_facilities
        called_tool = False
        message_text = None
        for _ in range(60):
            ev = result.expect.next_event()
            ev_obj = ev.event()
            name = getattr(getattr(ev_obj, "item", None), "name", None)
            if name == "find_nearby_health_facilities":
                called_tool = True
                break
            try:
                msg = ev.is_message(role="assistant")
                event = msg.event()
                content = event.item.content
                message_text = (
                    content[0]
                    if isinstance(content, list) and content
                    else str(content)
                )
                break  # first assistant message captured — stop draining
            except Exception:
                continue

        assert not called_tool, "LIVE TEST: FAIL — tool called without a location"
        assert message_text, "LIVE TEST: FAIL — no assistant response"
        assert (
            "city" in message_text.lower()
            or "district" in message_text.lower()
            or "location" in message_text.lower()
        ), f"LIVE TEST: FAIL — did not ask for location: {message_text[:120]}"
        print("LIVE TEST: PASS — agent asked for location before searching:")
        print("  ", message_text[:160])


@pytest.mark.asyncio
async def test_live_tool_selection_and_natural_response():
    """LIVE TEST — Gemini autonomously selects the tool and speaks naturally (no JSON)."""
    from livekit.agents import AgentSession
    from livekit.plugins import google

    from agent import Assistant

    async with (
        google.LLM(model="gemini-3.5-flash-lite") as llm_client,
        AgentSession(llm=llm_client) as session,
    ):
        await session.start(Assistant(user_id="saathi_live_day5"))

        result = await session.run(
            user_input="Saathi, I am in Navsari. Can you find a nearby health facility?"
        )

        called_name = None
        for _ in range(60):
            ev = result.expect.next_event()
            ev_obj = ev.event()
            name = getattr(getattr(ev_obj, "item", None), "name", None)
            if name == "find_nearby_health_facilities":
                ev.is_function_call(name="find_nearby_health_facilities")
                called_name = name
                break
        assert called_name == "find_nearby_health_facilities", (
            "LIVE TEST: FAIL — tool not selected"
        )

        # Grab the final assistant message and verify it is natural speech, not JSON.
        message_text = None
        for _ in range(60):
            ev = result.expect.next_event()
            try:
                msg = ev.is_message(role="assistant")
                event = msg.event()
                content = event.item.content
                message_text = (
                    content[0]
                    if isinstance(content, list) and content
                    else str(content)
                )
                break
            except Exception:
                continue
        assert message_text, "LIVE TEST: FAIL — no assistant message"
        assert "{" not in message_text and "[" not in message_text[:50], (
            "LIVE TEST: FAIL — agent read out JSON"
        )
        assert (
            "Navsari" in message_text
            or "facility" in message_text.lower()
            or "hospital" in message_text.lower()
        )
        print("LIVE TEST: PASS — tool selected, natural spoken response:")
        print("  ", message_text[:220])
