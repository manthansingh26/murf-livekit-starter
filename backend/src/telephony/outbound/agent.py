"""Day 6 — Saathi outbound follow-up agent (separate worker).

This worker handles OUTBOUND calls only. It registers a different agent name
(``saathi-outbound``) than the existing browser agent (``my-agent`` in
``src/agent.py``), so LiveKit only dispatches it to rooms created by the
outbound dialer (``telephony/outbound/dial.py``). The existing browser agent is
left completely untouched.

Call flow (official LiveKit agent-initiated outbound pattern):

    dial.py dispatches this agent into a fresh room with the destination
        ->  LiveKit Agent (this worker) starts in the room
        ->  ctx.api.sip.create_sip_participant(...) through the stored
            outbound SIP trunk (LIVEKIT_SIP_OUTBOUND_TRUNK_ID)
        ->  sip.linphone.org -> Linphone rings -> user answers
        ->  Saathi introduces itself (who / why / opt-out)
        ->  conversation -> user hangs up -> graceful shutdown
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_SRC_DIR = _BACKEND_DIR / "src"

# Make the existing `src/agent.py` importable as `agent` even though this file
# is ALSO named `agent.py`. `src/` MUST be at the FRONT of sys.path: the
# editable install already puts it on sys.path (via the .pth in site-packages),
# but that entry sits BEHIND this script's own directory, so `import agent`
# would otherwise resolve to THIS file (a self-import). Removing any existing
# entry and re-inserting at index 0 makes resolution deterministic and
# independent of the current working directory.
if str(_SRC_DIR) in sys.path:
    sys.path.remove(str(_SRC_DIR))
sys.path.insert(0, str(_SRC_DIR))

# backend/.env.local is the single authoritative local configuration.
load_dotenv(_BACKEND_DIR / ".env.local", override=True)

from livekit import api, rtc  # noqa: E402
from livekit.agents import (  # noqa: E402
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    llm,
    room_io,
    tokenize,
)
from livekit.plugins import google, murf, noise_cancellation, silero  # noqa: E402
from livekit.plugins.turn_detector.multilingual import (  # noqa: E402
    MultilingualModel,
)

# Reuse the exact multilingual STT and language detection from the existing
# browser agent — identical behavior, zero changes to the protected file.
from agent import MultilingualDeepgramSTT, detect_language  # noqa: E402
from analytics import CallAnalyticsTracker  # noqa: E402

logger = logging.getLogger("saathi-outbound")

# Must match AGENT_NAME in telephony/outbound/dial.py.
AGENT_NAME = "saathi-outbound"

OUTBOUND_SYSTEM_PROMPT = (
    "You are Saathi, a multilingual health-access assistant, making an "
    "OUTBOUND follow-up call.\n\n"
    "CALL CONTEXT:\n"
    "- You introduced yourself at the start of the call (who you are, why you "
    "are calling, and that the user can ask you to stop at any time).\n"
    "- Do not claim that a specific previous conversation or health event "
    "exists. If the user does not recognize you, politely re-introduce "
    "yourself and ask how you can help.\n\n"
    "BEHAVIOR:\n"
    "- Ask how the user is feeling and whether they need help accessing "
    "health services. You can provide general health-access guidance and "
    "navigation help only.\n"
    "- You are NOT a doctor. Never diagnose, prescribe medication, invent "
    "medical information, or create false urgency.\n"
    "- If the user reports an emergency, tell them to contact their local "
    "emergency services immediately.\n"
    "- If the user declines to talk or asks you to stop, respect that "
    "immediately, thank them warmly, and end the conversation gracefully.\n"
    "- Never store, save, or record any personal information shared during "
    "this call.\n\n"
    "LANGUAGE:\n"
    "- Respond in the language the user speaks.\n"
    "- English -> English (Latin script); Hindi -> Devanagari script "
    "(e.g. namaste written as \u0928\u092e\u0938\u094d\u0924\u0947); Gujarati -> "
    "Gujarati script (e.g. namaste written as \u0aa8\u0aae\u0ab8\u0acd\u0aa4\u0ac7).\n"
    "- Never romanize Hindi or Gujarati. A system instruction with the "
    "detected language is appended to every user turn — always follow it."
)

OPENING_INSTRUCTIONS = (
    "Say the following opening naturally, in a warm tone, and then stop and "
    "wait for the user to respond:\n"
    "'Hello, this is Saathi, your health access assistant. I'm calling to "
    "follow up on our previous conversation and check in on you. Is this a "
    "good time to talk? You can tell me to stop at any time and I will end "
    "the call.'"
)


def _log_sip_failure(exc: Exception) -> None:
    """Log an outbound dial failure with sanitized SIP status info."""
    status = getattr(exc, "sip_status_code", None)
    reason = getattr(exc, "sip_status", None)
    if status is None and reason is None:
        reason = str(exc)
    logger.error(
        f"[DAY6 OUTBOUND] Call failed status={status or 'n/a'} reason={reason}"
    )


class OutboundFollowUpAgent(Agent):
    """Simple, safe outbound follow-up agent (no memory, no medical claims)."""

    def __init__(self) -> None:
        super().__init__(instructions=OUTBOUND_SYSTEM_PROMPT)

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        if new_message and new_message.text_content:
            detected = detect_language(new_message.text_content)

            logger.info("[DAY6 OUTBOUND] TURN DIAGNOSTIC")
            logger.info(f"Transcript: {new_message.text_content}")
            logger.info(f"Language: {detected}")

            if detected == "Gujarati":
                lang_inst = (
                    "\n\n[SYSTEM INSTRUCTION: The user's current utterance is "
                    "classified as GUJARATI. You MUST respond in natural "
                    "Gujarati using the Gujarati script. Do NOT respond in "
                    "Hindi or Romanized Gujarati. Preserve English medical "
                    "terms natively.]"
                )
            elif detected == "Hindi":
                lang_inst = (
                    "\n\n[SYSTEM INSTRUCTION: The user's current utterance is "
                    "classified as HINDI. You MUST respond in natural Hindi "
                    "using the Devanagari script. Do NOT respond in Gujarati "
                    "or Romanized Hindi. Preserve English medical terms "
                    "natively.]"
                )
            else:
                lang_inst = (
                    "\n\n[SYSTEM INSTRUCTION: The user's current utterance is "
                    "classified as ENGLISH. You MUST respond in natural "
                    "English using the Latin script. Do NOT respond in Hindi "
                    "or Gujarati.]"
                )

            new_message.content.append(lang_inst)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name=AGENT_NAME)
async def saathi_outbound(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    logger.info("==================================================")
    logger.info("[DAY6 OUTBOUND] Outbound agent job started")

    # 1. The destination comes from the dispatch metadata written by dial.py.
    destination = None
    try:
        meta = json.loads(ctx.job.metadata or "{}")
        destination = (meta.get("to") or "").strip() or None
    except Exception:
        logger.error(
            "[DAY6 OUTBOUND] Invalid dispatch metadata - cannot parse destination."
        )

    trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

    logger.info(f"[DAY6 OUTBOUND] Trunk configured: {'YES' if trunk_id else 'NO'}")
    logger.info(
        f"[DAY6 OUTBOUND] Destination configured: {'YES' if destination else 'NO'}"
    )

    if not trunk_id or not destination:
        logger.error(
            "[DAY6 OUTBOUND] Missing trunk ID or destination "
            f"(trunk_configured={'YES' if trunk_id else 'NO'} "
            f"destination_configured={'YES' if destination else 'NO'}). "
            "Aborting call."
        )
        ctx.shutdown()
        return

    await ctx.connect()

    # 2. Place the outbound call through the stored outbound SIP trunk.
    sip_identity = f"saathi-sip-{uuid.uuid4().hex[:8]}"
    logger.info("[DAY6 OUTBOUND] Creating SIP participant...")
    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=trunk_id,
                sip_call_to=destination,
                room_name=ctx.room.name,
                participant_identity=sip_identity,
                participant_name="Saathi outbound callee",
                wait_until_answered=True,
            )
        )
    except Exception as e:
        _log_sip_failure(e)
        ctx.shutdown()
        return

    logger.info("[DAY6 OUTBOUND] Call answered successfully")

    # 3. Wait for the SIP participant to fully join, then start the session.
    #    A timeout guards against the edge case where the call was answered but
    #    the participant never actually joins the room.
    try:
        participant = await asyncio.wait_for(
            ctx.wait_for_participant(identity=sip_identity), timeout=60
        )
    except asyncio.TimeoutError:
        logger.error(
            "[DAY6 OUTBOUND] Call answered but callee never joined the room - "
            "aborting call."
        )
        ctx.shutdown()
        return
    logger.info(
        f"[DAY6 OUTBOUND] Callee joined as participant identity={participant.identity}"
    )

    session = AgentSession(
        stt=MultilingualDeepgramSTT(),
        llm=google.LLM(model="gemini-3.5-flash-lite"),
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Day 8 — call analytics (additive). Fail-soft: analytics failures are only
    # logged and can never delay or break the outbound call. No personal data
    # is ever stored — the outbound privacy contract forbids it.
    tracker = CallAnalyticsTracker(call_id=ctx.room.name, channel="sip")
    await tracker.record_start()
    tracker.wire(session)

    # 4. Gracefully end when the callee hangs up.
    def _on_participant_disconnected(
        disconnected: rtc.RemoteParticipant, _reason: rtc.DisconnectReason
    ) -> None:
        logger.info(
            f"[DAY6 OUTBOUND] Participant disconnected "
            f"({disconnected.identity}) - ending call"
        )
        ctx.shutdown("Callee hung up")

    ctx.room.on("participant_disconnected", _on_participant_disconnected)

    await session.start(
        agent=OutboundFollowUpAgent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind
                    == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )

    # 5. Opening message (who / why / opt-out). Spoken only after the callee
    #    has answered and joined, so nothing is played into dead air.
    await session.generate_reply(instructions=OPENING_INSTRUCTIONS)


if __name__ == "__main__":
    cli.run_app(server)
