"""Day 6 outbound calling — unit tests.

These tests NEVER place a real call. They cover the pure dial/agent logic:

- destination (sip_call_to) normalization for Linphone
- outbound system-prompt safety (opt-out, no medical authority, multilingual)
- agent-name consistency between dialer and agent
- SIP failure logging is defensive
- required outbound env var is configured locally
"""

import logging
import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_SRC_DIR = _BACKEND_DIR / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from telephony.outbound import agent as outbound_agent  # noqa: E402
from telephony.outbound.dial import AGENT_NAME, normalize_destination  # noqa: E402

# ---------------------------------------------------------------------------
# Destination normalization (sip_call_to)
# ---------------------------------------------------------------------------


def test_normalize_destination_bare_username():
    # A bare Linphone username is the SIP user itself — never wrapped in a URI.
    assert normalize_destination("my-linphone-user") == "my-linphone-user"


def test_normalize_destination_strips_whitespace():
    assert normalize_destination("  my-linphone-user  ") == "my-linphone-user"


def test_normalize_destination_full_sip_uri_reduced_to_user():
    # LiveKit rejects full SIP URIs for sip_call_to — reduce to the user only.
    assert (
        normalize_destination("sip:my-linphone-user@sip.linphone.org")
        == "my-linphone-user"
    )


def test_normalize_destination_host_qualified_reduced_to_user():
    assert (
        normalize_destination("my-linphone-user@sip.linphone.org")
        == "my-linphone-user"
    )


def test_normalize_destination_phone_number_untouched():
    assert normalize_destination("+15551234567") == "+15551234567"


def test_cli_username_never_becomes_full_sip_uri():
    """Regression: --to <username> must yield a SIP user for sip_call_to, never
    a full SIP URI (the API rejects those with SipCallTo invalid_argument)."""
    for raw in (
        "saathi-user",
        "saathi-user@sip.linphone.org",
        "sip:saathi-user@sip.linphone.org",
    ):
        out = normalize_destination(raw)
        assert out == "saathi-user"
        assert ":" not in out  # no scheme
        assert "@" not in out  # no domain


# ---------------------------------------------------------------------------
# Outbound agent configuration
# ---------------------------------------------------------------------------


def test_dialer_and_agent_share_agent_name():
    assert outbound_agent.AGENT_NAME == AGENT_NAME == "saathi-outbound"


def test_outbound_server_registers_rtc_session():
    assert callable(getattr(outbound_agent, "saathi_outbound", None))


def test_outbound_prompt_identifies_and_allows_opt_out():
    prompt = outbound_agent.OUTBOUND_SYSTEM_PROMPT.lower()
    assert "saathi" in prompt
    assert "stop" in prompt


def test_outbound_prompt_does_not_claim_medical_authority():
    prompt = outbound_agent.OUTBOUND_SYSTEM_PROMPT.lower()
    # The prompt refuses clinical authority instead of claiming it.
    assert "i am a doctor" not in prompt
    assert "i can diagnose" not in prompt
    assert "i can prescribe" not in prompt
    assert "not a doctor" in prompt


def test_outbound_prompt_handles_emergencies_safely():
    prompt = outbound_agent.OUTBOUND_SYSTEM_PROMPT.lower()
    assert "emergency services" in prompt


def test_outbound_prompt_is_multilingual():
    prompt = outbound_agent.OUTBOUND_SYSTEM_PROMPT.lower()
    assert "hindi" in prompt
    assert "gujarati" in prompt
    assert "english" in prompt
    # Native scripts must be preserved (Devanagari + Gujarati examples).
    assert (
        "\u0928\u092e\u0938\u094d\u0924\u0947" in outbound_agent.OUTBOUND_SYSTEM_PROMPT
    )
    assert (
        "\u0aa8\u0aae\u0ab8\u0acd\u0aa4\u0ac7" in outbound_agent.OUTBOUND_SYSTEM_PROMPT
    )


def test_opening_instructions_cover_who_why_opt_out():
    opening = outbound_agent.OPENING_INSTRUCTIONS.lower()
    assert "saathi" in opening
    assert "follow up" in opening
    assert "stop" in opening


# ---------------------------------------------------------------------------
# Failure logging (sanitized, defensive)
# ---------------------------------------------------------------------------


def test_sip_failure_logging_sip_style_error(caplog):
    class FakeSipError(Exception):
        sip_status_code = 486
        sip_status = "Busy Here"

    with caplog.at_level(logging.ERROR):
        outbound_agent._log_sip_failure(FakeSipError("hidden detail"))

    assert "Call failed" in caplog.text
    assert "status=486" in caplog.text
    assert "Busy Here" in caplog.text


def test_sip_failure_logging_generic_error(caplog):
    with caplog.at_level(logging.ERROR):
        outbound_agent._log_sip_failure(RuntimeError("connection refused"))

    assert "Call failed" in caplog.text
    assert "status=n/a" in caplog.text
    assert "connection refused" in caplog.text


# ---------------------------------------------------------------------------
# Environment configuration (names only, never values)
# ---------------------------------------------------------------------------


def test_outbound_env_configured():
    env_file = _BACKEND_DIR / ".env.local"
    if not env_file.exists():
        pytest.skip("backend/.env.local not present")

    load_dotenv(env_file, override=True)
    assert os.getenv("LIVEKIT_URL"), "LIVEKIT_URL must be set"
    assert os.getenv("LIVEKIT_API_KEY"), "LIVEKIT_API_KEY must be set"
    assert os.getenv("LIVEKIT_API_SECRET"), "LIVEKIT_API_SECRET must be set"
    assert os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID"), (
        "LIVEKIT_SIP_OUTBOUND_TRUNK_ID must be set"
    )
