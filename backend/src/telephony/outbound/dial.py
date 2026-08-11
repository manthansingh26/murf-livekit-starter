#!/usr/bin/env python3
"""Day 6 — Saathi outbound call dialer.

Places ONE outbound call to a Linphone destination. The dialer only dispatches
the Saathi outbound agent (``telephony/outbound/agent.py``) into a fresh room
with the destination in the job metadata; the agent then places the call
through the stored LiveKit outbound SIP trunk (``LIVEKIT_SIP_OUTBOUND_TRUNK_ID``)
using the official agent-initiated outbound pattern.

Usage:
    uv run python src/telephony/outbound/dial.py --to <your-linphone-username>

The destination may be a bare Linphone username (``myuser``), a phone number
(``+15551234567``), or an already-qualified destination
(``sip:myuser@sip.linphone.org``) — qualified destinations are normalized down
to the SIP user/phone number because LiveKit's ``sip_call_to`` rejects full SIP
URIs. No real call is placed by this script itself — the outbound agent must be
running in another terminal for the call to actually ring.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from livekit import api

_BACKEND_DIR = Path(__file__).resolve().parents[3]
# backend/.env.local is the single authoritative local configuration.
load_dotenv(_BACKEND_DIR / ".env.local", override=True)

logger = logging.getLogger("saathi-outbound")

# Must match AGENT_NAME in telephony/outbound/agent.py.
AGENT_NAME = "saathi-outbound"
ROOM_PREFIX = "saathi-outbound-"


def normalize_destination(to: str) -> str:
    """Return the value to pass to ``create_sip_participant(sip_call_to=...)``.

    LiveKit's ``sip_call_to`` accepts a phone number (E.164) or a SIP user -
    NOT a full SIP URI (the API rejects e.g. ``sip:myuser@sip.linphone.org``
    with ``SipCallTo should be a phone number or SIP user, not a full SIP URI``).
    The SIP domain (e.g. sip.linphone.org) is configured on the LiveKit outbound
    trunk itself, so it is never embedded in the destination here:

        "myuser"                          -> "myuser"        (SIP user)
        "  myuser  "                      -> "myuser"
        "myuser@sip.linphone.org"         -> "myuser"        (user only)
        "sip:myuser@sip.linphone.org"     -> "myuser"        (user only)
        "+15551234567"                    -> "+15551234567"  (phone, untouched)
    """
    to = to.strip()
    if to.lower().startswith("sip:"):
        to = to[4:].strip()
    # The trunk owns the domain; keep only the SIP user / phone number.
    return to.split("@", 1)[0].strip()


async def main(to: str) -> int:
    trunk_id = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")
    destination = normalize_destination(to)

    logger.info("[DAY6 OUTBOUND] Starting outbound call")
    logger.info(
        f"[DAY6 OUTBOUND] LIVEKIT_URL configured: {'YES' if os.getenv('LIVEKIT_URL') else 'NO'}"
    )
    logger.info(
        f"[DAY6 OUTBOUND] LIVEKIT_API_KEY configured: {'YES' if os.getenv('LIVEKIT_API_KEY') else 'NO'}"
    )
    logger.info(
        f"[DAY6 OUTBOUND] LIVEKIT_API_SECRET configured: {'YES' if os.getenv('LIVEKIT_API_SECRET') else 'NO'}"
    )
    logger.info(f"[DAY6 OUTBOUND] Trunk configured: {'YES' if trunk_id else 'NO'}")
    logger.info(
        f"[DAY6 OUTBOUND] Destination configured: {'YES' if destination else 'NO'}"
    )

    missing = [
        name
        for name in ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
        if not os.getenv(name)
    ]
    if missing:
        logger.error(
            "[DAY6 OUTBOUND] Missing required environment variable(s): "
            f"{', '.join(missing)}. Aborting."
        )
        return 1
    if not trunk_id:
        logger.error(
            "[DAY6 OUTBOUND] LIVEKIT_SIP_OUTBOUND_TRUNK_ID is not set in "
            "backend/.env.local. Aborting."
        )
        return 1
    if not destination:
        logger.error("[DAY6 OUTBOUND] --to destination is empty. Aborting.")
        return 1

    room_name = f"{ROOM_PREFIX}{uuid.uuid4().hex[:8]}"
    metadata = json.dumps({"to": destination})

    logger.info(
        f"[DAY6 OUTBOUND] Dispatching agent '{AGENT_NAME}' into room {room_name}"
    )
    logger.info(f"[DAY6 OUTBOUND] Destination: {destination}")

    async with api.LiveKitAPI() as lkapi:
        await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata,
            )
        )

    logger.info(
        "[DAY6 OUTBOUND] Agent dispatched. Waiting for the call to ring and "
        "be answered..."
    )
    logger.info(
        "[DAY6 OUTBOUND] Watch the OUTBOUND AGENT terminal for the call outcome."
    )
    return 0


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place ONE Saathi outbound call to a Linphone destination."
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Linphone username (e.g. myuser), phone number (e.g. +15551234567), "
        "or full SIP destination (e.g. sip:myuser@sip.linphone.org).",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    sys.exit(asyncio.run(main(args.to)))
