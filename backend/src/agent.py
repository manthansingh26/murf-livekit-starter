import json
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
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
from livekit.plugins import deepgram, google, murf, noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from db import db_target_info, init_db, lookup_caller
from prompts import SAATHI_SYSTEM_PROMPT
from tools.escalation import EscalationTools
from tools.health_access import HealthAccessTools
from tools.human_escalation import HumanEscalationTools, detect_escalation_trigger
from tools.memory import MemoryTools
from tools.triage import TriageTools

logger = logging.getLogger("agent")

# Load backend/.env.local by ABSOLUTE path so the process works no matter which
# directory it is launched from (terminal, IDE, start_app.ps1, etc.). override=True
# makes backend/.env.local the single authoritative local configuration.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(_BACKEND_DIR / ".env.local", override=True)
load_dotenv(".env.local")  # fallback for other relative configs

from livekit.agents import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, stt  # noqa: E402


class MultilingualDeepgramStream(stt.RecognizeStream):
    def __init__(self, stt_instance, conn_options, stream_multi, stream_gu):
        super().__init__(stt=stt_instance, conn_options=conn_options)
        self._stream_multi = stream_multi
        self._stream_gu = stream_gu

    def push_frame(self, frame: rtc.AudioFrame) -> None:
        super().push_frame(frame)
        self._stream_multi.push_frame(frame)
        self._stream_gu.push_frame(frame)

    def flush(self) -> None:
        super().flush()
        self._stream_multi.flush()
        self._stream_gu.flush()

    def end_input(self) -> None:
        super().end_input()
        self._stream_multi.end_input()
        self._stream_gu.end_input()

    async def aclose(self) -> None:
        await self._stream_multi.aclose()
        await self._stream_gu.aclose()
        await super().aclose()

    async def _run(self) -> None:
        import asyncio

        async def run_multi():
            async for ev in self._stream_multi:
                if ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    text_multi = (
                        ev.alternatives[0].text
                        if (ev.alternatives and len(ev.alternatives) > 0)
                        else ""
                    )

                    latin_chars = len(re.findall(r"[a-zA-Z]", text_multi))
                    hindi_chars = len(re.findall(r"[\u0900-\u097F]", text_multi))
                    total_words = len(text_multi.split())
                    latin_words = len(re.findall(r"\b[a-zA-Z]+\b", text_multi))

                    hindi_markers = [
                        "मेरा",
                        "मेरी",
                        "मेरे",
                        "मुझे",
                        "आप",
                        "आपका",
                        "आपकी",
                        "है",
                        "हैं",
                        "क्या",
                        "नहीं",
                        "था",
                        "थी",
                        "थे",
                        "हुआ",
                        "हुई",
                        "कैसा",
                        "कैसी",
                        "कैसे",
                        "सब",
                        "हम",
                        "हमारे",
                    ]
                    has_hindi_marker = any(w in text_multi for w in hindi_markers)

                    # English or Hindi from multi stream always takes priority over phonetic gujarati transliteration
                    if (
                        latin_words > 0
                        and (
                            latin_words >= total_words * 0.4
                            or latin_chars > hindi_chars
                        )
                    ) or (hindi_chars > 0 and has_hindi_marker):
                        self._event_ch.send_nowait(ev)
                else:
                    self._event_ch.send_nowait(ev)

        async def run_gu():
            async for ev in self._stream_gu:
                if ev.type == stt.SpeechEventType.FINAL_TRANSCRIPT:
                    text_gu = (
                        ev.alternatives[0].text
                        if (ev.alternatives and len(ev.alternatives) > 0)
                        else ""
                    )
                    gujarati_chars = len(re.findall(r"[\u0A80-\u0AFF]", text_gu))
                    if gujarati_chars > 0:
                        self._event_ch.send_nowait(ev)

        await asyncio.gather(run_multi(), run_gu())


class MultilingualDeepgramSTT(stt.STT):
    def __init__(self, api_key: str | None = None):
        super().__init__(
            capabilities=stt.STTCapabilities(streaming=True, interim_results=True)
        )
        api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            load_dotenv(".env.local")
            api_key = os.getenv("DEEPGRAM_API_KEY")
        self._stt_multi = deepgram.STT(
            model="nova-3", language="multi", api_key=api_key
        )
        self._stt_gu = deepgram.STT(model="nova-3", language="gu", api_key=api_key)

    async def _recognize_impl(
        self, buffer, *, language=NOT_GIVEN, conn_options=DEFAULT_API_CONNECT_OPTIONS
    ):
        return await self._stt_multi._recognize_impl(
            buffer, language=language, conn_options=conn_options
        )

    def stream(self, *, language=NOT_GIVEN, conn_options=DEFAULT_API_CONNECT_OPTIONS):
        s_multi = self._stt_multi.stream(language=language, conn_options=conn_options)
        s_gu = self._stt_gu.stream(language=language, conn_options=conn_options)
        return MultilingualDeepgramStream(self, conn_options, s_multi, s_gu)


def detect_language(text: str) -> str:
    """
    Detects dominant language based on Unicode script ranges and Hindi marker words.
    Returns: 'Hindi', 'Gujarati', or 'English'
    """
    if not text:
        return "English"

    gujarati_chars = len(re.findall(r"[\u0A80-\u0AFF]", text))
    hindi_chars = len(re.findall(r"[\u0900-\u097F]", text))
    latin_words = len(re.findall(r"\b[a-zA-Z]+\b", text))
    total_words = len(text.split())

    if latin_words > 0 and (
        latin_words >= total_words * 0.4 or latin_words > gujarati_chars
    ):
        return "English"
    elif gujarati_chars > hindi_chars and gujarati_chars > 0:
        return "Gujarati"
    elif hindi_chars > 0:
        return "Hindi"
    else:
        return "English"


def analyze_consent_turn(text: str) -> str:
    text_lower = text.lower()

    info_patterns = [
        r"\bmy name is\b",
        r"\bi am\b",
        r"\bname\'s\b",
        r"\byears old\b",
        r"\bage is\b",
        r"मेरा नाम",
        r"मेरी उम्र",
        r"मैं .* हूँ",
        r"महीने",
        r"साल",
        r"મારું નામ",
        r"મારી ઉંમર",
        r"હું .* છું",
    ]
    has_info = any(re.search(p, text_lower, re.IGNORECASE) for p in info_patterns)

    save_patterns = [
        r"\bremember\b",
        r"\bsave\b",
        r"\bstore\b",
        r"\bkeep\b",
        r"याद",
        r"सहेज",
        r"સેવ",
        r"યાદ",
        r"સાચવો",
    ]
    has_explicit_save = any(
        re.search(p, text_lower, re.IGNORECASE) for p in save_patterns
    )

    no_patterns = [
        r"\bno\b",
        r"\bdon\'t\b",
        r"\bdo not\b",
        r"\bnever\b",
        r"\bno thanks\b",
        r"नहीं",
        r"नही",
        r"ना",
        r"मत",
        r"ના",
        r"નથી",
        r"નહી",
    ]
    has_no = any(re.search(p, text_lower, re.IGNORECASE) for p in no_patterns)

    yes_patterns = [
        r"\byes\b",
        r"\byeah\b",
        r"\byep\b",
        r"\bsure\b",
        r"\bokay\b",
        r"\bok\b",
        r"\bplease do\b",
        r"\bremember it\b",
        r"\bsave it\b",
        r"हाँ",
        r"हा",
        r"जी",
        r"ज़रूर",
        r"હા",
        r"ચોક્કસ",
    ]
    has_yes = any(re.search(p, text_lower, re.IGNORECASE) for p in yes_patterns)

    if has_info:
        if has_explicit_save:
            return "EXPLICIT_SAVE_REQUESTED"
        else:
            return "PROACTIVE_CONSENT_REQUIRED"
    elif has_no:
        return "CONSENT_REJECTED"
    elif has_yes:
        return "CONSENT_GRANTED"
    else:
        return "NORMAL_TURN"


def format_returning_caller_instruction(record: dict) -> str:
    """Build the deterministic SYSTEM INSTRUCTION block from a caller_memory record.

    The record is loaded from PostgreSQL (through the existing memory system) at the
    start of the call. This is a dynamic per-turn instruction — NOT a hardcoded prompt
    result — so the agent greets the returning caller by name on the very first turn.
    """
    name = record.get("name") or ""
    language_pref = record.get("language_preference") or ""
    facts = record.get("facts") or {}
    if isinstance(facts, str):
        try:
            facts = json.loads(facts)
        except Exception:
            facts = {}
    facts_str = ", ".join(f"{k}: {v}" for k, v in facts.items() if v)

    parts = []
    if name:
        parts.append(f"name: {name}")
    if language_pref:
        parts.append(f"language_preference: {language_pref}")
    if facts_str:
        parts.append(f"known_facts: {facts_str}")

    if name:
        greeting = (
            "You MUST greet them warmly BY NAME "
            f"(e.g. 'Welcome back, {name}. How can I help you today?') and DO NOT ask them "
            "for their name — it is already known."
        )
    else:
        greeting = (
            "They have not shared a name yet — greet them warmly as a returning caller "
            "and ask how they are feeling today."
        )

    return (
        "\n\n[SYSTEM INSTRUCTION: The caller profile for this session was loaded from the "
        f"database. Profile — {'; '.join(parts) or 'no stored fields'}. "
        "This is a RETURNING CALLER. "
        f"{greeting} "
        "Respond in the same language and script as the user's CURRENT turn.]"
    )


class Assistant(
    Agent,
    TriageTools,
    EscalationTools,
    MemoryTools,
    HealthAccessTools,
    HumanEscalationTools,
):
    def __init__(self, user_id: str = "default_user") -> None:
        super().__init__(instructions=SAATHI_SYSTEM_PROMPT.format(user_id=user_id))
        self.user_id = user_id
        self._memory_injected = False
        # Day 7: remembers which escalation offer (red_flag_symptom /
        # diagnosis_request) is pending, so an explicit YES later triggers
        # create_escalation deterministically (never on a red flag alone).
        self._pending_escalation_trigger = None

    async def _inject_caller_memory(self, new_message: llm.ChatMessage) -> None:
        """Deterministic returning-caller memory lookup, run ONCE on the first user turn.

        Loads the caller profile from PostgreSQL through the existing memory system and
        appends a SYSTEM INSTRUCTION so the agent KNOWS the caller before generating its
        first response — no reliance on the LLM randomly deciding to call a tool.

        NOTE: The LLM may additionally call the `lookup_caller_memory` tool because the
        system prompt asks it to — that redundant read is intentional (belt and braces)
        and must not replace this deterministic path.
        """
        if self._memory_injected:
            return
        self._memory_injected = True

        try:
            record = await lookup_caller(self.user_id)
        except Exception as e:
            logger.error(
                f"[MEMORY DEBUG] lookup_result=ERROR user_id={self.user_id} reason={e}"
            )
            return

        if record:
            logger.info(
                f"[MEMORY DEBUG] lookup_result=FOUND user_id={self.user_id} "
                f"name={record.get('name')}"
            )
            new_message.content.append(format_returning_caller_instruction(record))
        else:
            logger.info(
                f"[MEMORY DEBUG] lookup_result=NOT_FOUND user_id={self.user_id}"
            )

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        if new_message and new_message.text_content:
            await self._inject_caller_memory(new_message)

            detected = detect_language(new_message.text_content)
            consent_action = analyze_consent_turn(new_message.text_content)

            logger.info("----------------------------------------")
            logger.info("TURN DIAGNOSTICS")
            logger.info(f"Caller ID: {self.user_id}")
            logger.info(f"Transcript: {new_message.text_content}")
            logger.info(f"Language: {detected}")
            logger.info(f"Consent Action: {consent_action}")
            logger.info("----------------------------------------")

            if detected == "Gujarati":
                lang_inst = "\n\n[SYSTEM INSTRUCTION: The user's current utterance is classified as GUJARATI. You MUST respond in natural Gujarati using the Gujarati script. Do NOT respond in Hindi or Romanized Gujarati. Preserve English medical terms natively.]"
            elif detected == "Hindi":
                lang_inst = "\n\n[SYSTEM INSTRUCTION: The user's current utterance is classified as HINDI. You MUST respond in natural Hindi using the Devanagari script. Do NOT respond in Gujarati or Romanized Hindi. Preserve English medical terms natively.]"
            else:
                lang_inst = "\n\n[SYSTEM INSTRUCTION: The user's current utterance is classified as ENGLISH. You MUST respond in natural English using the Latin script. Do NOT respond in Hindi or Gujarati.]"

            consent_inst = ""
            if consent_action == "PROACTIVE_CONSENT_REQUIRED":
                consent_inst = (
                    "\n\n[CRITICAL CONSENT RULE: The user provided personal information (such as name or age) BUT HAS NOT GIVEN CONSENT TO SAVE IT YET. "
                    "DO NOT CALL save_caller_memory. "
                    "You MUST acknowledge their information warmly AND explicitly ask for permission to save it for future conversations before doing anything else. "
                    "Example: 'Nice to meet you, Manthan. I can remember your name and age for future conversations. Would you like me to save them?']"
                )
            elif consent_action == "EXPLICIT_SAVE_REQUESTED":
                consent_inst = (
                    "\n\n[CONSENT RULE: The user explicitly requested to save/remember their information in this turn (e.g. 'remember my name'). "
                    f"You MAY call save_caller_memory now with user_id='{self.user_id}' and the provided facts, and confirm naturally.]"
                )
            elif consent_action == "CONSENT_GRANTED":
                consent_inst = (
                    "\n\n[CONSENT RULE: The user explicitly GRANTED PERMISSION to save their information. "
                    f"You MUST call save_caller_memory now with user_id='{self.user_id}' and the facts provided previously in the conversation, and confirm naturally.]"
                )
            elif consent_action == "CONSENT_REJECTED":
                consent_inst = (
                    "\n\n[CRITICAL CONSENT RULE: The user explicitly REJECTED saving their information (said NO / don't save). "
                    "DO NOT CALL save_caller_memory under any circumstances. "
                    "Reply politely acknowledging their choice (e.g. 'No problem, I won't save that.').]"
                )

            # ---- DAY 7: HUMAN ESCALATION DETERMINISTIC FLOW ----
            # Same per-turn injection pattern as the language/consent rules above,
            # so a red-flag or diagnosis-request turn ALWAYS ends with the
            # human-help offer + consent question (never stops at the emergency
            # guidance alone), and an explicit YES always reaches create_escalation.
            escalation_inst = ""
            trigger = detect_escalation_trigger(new_message.text_content)
            if self._pending_escalation_trigger and consent_action == "CONSENT_GRANTED":
                # The caller just said YES to the human-help offer made earlier.
                # Checked BEFORE a new trigger so a granted consent is never
                # overwritten by a re-detected trigger in the same turn.
                reason = self._pending_escalation_trigger
                self._pending_escalation_trigger = None
                escalation_inst = (
                    "\n\n[DAY 7 CONSENT: The caller just granted explicit permission for the "
                    "human-help escalation you offered earlier. You MUST call `create_escalation` "
                    f"NOW with consent_confirmed=True, user_id='{self.user_id}', "
                    f"reason='{reason}', and the other fields as follows. "
                    "Provide a SHORT 2-3 sentence summary in what_happened (never the full "
                    "transcript, never passwords/OTPs/PINs/account numbers), an appropriate "
                    "urgency, the caller's language, and what you advised in agent_action. "
                    "Then confirm naturally and quote the reference ID you receive, without "
                    "promising an immediate callback or a guaranteed response time.]"
                )
            elif self._pending_escalation_trigger and consent_action == "CONSENT_REJECTED":
                # The caller declined the human-help offer — no escalation, no
                # lingering pending state.
                self._pending_escalation_trigger = None
            elif trigger == "red_flag_symptom":
                self._pending_escalation_trigger = trigger
                escalation_inst = (
                    "\n\n[CRITICAL DAY 7 RULE: A red-flag emergency was detected in this turn. "
                    "Your response MUST include BOTH of these IN THE SAME RESPONSE: "
                    "(1) the emergency guidance — tell the caller to call 112 or 108 for an "
                    "ambulance immediately, or go to the nearest hospital right now; "
                    "(2) IMMEDIATELY AFTER the emergency guidance, offer human help and ask "
                    "for explicit permission, e.g. 'I can send a short summary of what you "
                    "told me to a human support person. Would you like me to do that?' "
                    "Do NOT end your response after the emergency guidance alone. Asking for "
                    "permission is NOT a symptom follow-up question. "
                    "Do NOT call create_escalation yet — wait for the caller's explicit YES.]"
                )
            elif trigger == "diagnosis_request":
                self._pending_escalation_trigger = trigger
                escalation_inst = (
                    "\n\n[CRITICAL DAY 7 RULE: The caller asked you to diagnose them. "
                    "You MUST NOT provide a diagnosis. In this SAME response: "
                    "(1) state that you are not a doctor and cannot diagnose them; "
                    "(2) offer human assistance and ask for explicit permission, e.g. "
                    "'I can send a short summary to a human support person who may be able "
                    "to help. Would you like me to do that?' "
                    "Do NOT call create_escalation yet — wait for the caller's explicit YES.]"
                )

            new_message.content.append(lang_inst + consent_inst + escalation_inst)


server = AgentServer()


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


server.setup_fnc = prewarm


@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        stt=MultilingualDeepgramSTT(),
        llm=google.LLM(
            model="gemini-3.5-flash-lite",
        ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
            voice="Anisha",
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True,
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Initialize Database Connection
    await init_db()

    # Join the room and connect
    await ctx.connect()

    # Wait for the remote participant to join and retrieve their persistent identity
    participant = await ctx.wait_for_participant()
    caller_id = participant.identity or "unknown_caller"

    db_host, db_port, db_name = db_target_info()

    logger.info("==================================================")
    logger.info("CALLER MEMORY DIAGNOSTIC")
    logger.info(f"session_id={id(session)}")
    logger.info(f"room={ctx.room.name}")
    logger.info(f"participant_identity={participant.identity}")
    logger.info(f"caller_id={caller_id}")
    logger.info(f"user_id={caller_id}")
    logger.info(f"db_host={db_host}")
    logger.info(f"db_port={db_port}")
    logger.info(f"db_name={db_name}")
    logger.info("==================================================")

    # Start the session with the Assistant configured with the persistent caller_id
    await session.start(
        agent=Assistant(user_id=caller_id),
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


if __name__ == "__main__":
    cli.run_app(server)
