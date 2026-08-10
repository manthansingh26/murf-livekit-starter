"""Day 5 — Health Access tool: find_nearby_health_facilities.

Retrieves REAL nearby health facilities from the public OpenStreetMap
dataset (Nominatim geocoder + Overpass API). The tool never fabricates
results: every failure mode returns an explicit structured error so the
agent can tell the caller honestly instead of inventing a facility.

Reliability design (added after live 504s were observed on the primary
Overpass endpoint):
- Multiple public Overpass endpoints with bounded failover (max one attempt
  per endpoint, small delay between attempts — never hammering public APIs).
- A shared, lazily-created httpx client with an explicit User-Agent and
  Accept headers, plus redirect following.
- In-memory geocode cache (TTL) so Nominatim is not re-queried for the same
  location during one conversation.
- Error results carry NO `retrieved_at` field — only successful lookups do,
  so the agent can never claim data was retrieved after a failure.
"""

import asyncio
import json
import logging
import math
import time
from contextlib import suppress
from datetime import datetime, timezone

import httpx
from livekit.agents import RunContext, function_tool

logger = logging.getLogger("health_access_tool")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Primary + legitimate public mirrors. Try each once, in order.
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
USER_AGENT = "SaathiHealthAssistant/1.0 (Health Access voice agent)"
DEFAULT_RADIUS_M = 5000
HTTP_TIMEOUT_S = 25  # Overpass mirrors can be slow — be generous but bounded
RETRY_DELAY_S = 0.6  # small polite delay between endpoint failovers
GEOCODE_CACHE_TTL_S = 600  # 10 minutes
MAX_RESULTS = 5

# Canonical facility types -> OpenStreetMap amenity/healthcare tag values.
FACILITY_TYPE_TAGS = {
    "hospital": ["hospital"],
    "clinic": ["clinic"],
    "health centre": ["clinic", "doctors"],
    "health center": ["clinic", "doctors"],
    "phc": ["clinic", "doctors"],
    "pharmacy": ["pharmacy"],
    "doctor": ["doctors"],
}
DEFAULT_TAGS = ["hospital", "clinic", "doctors", "pharmacy"]


class OverpassQueryError(Exception):
    """Overpass returned an error remark inside an otherwise-200 response."""


# --- HTTP plumbing -----------------------------------------------------------

_test_transport: httpx.AsyncBaseTransport | None = None  # tests inject MockTransport
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Shared lazy httpx client. Reuses connections across tool calls."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_S,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            follow_redirects=True,
            transport=_test_transport,  # None -> default (real network)
        )
    return _client


async def _close_client() -> None:
    global _client
    if _client is not None:
        with suppress(Exception):
            await _client.aclose()
        _client = None


# --- Geocoding (Nominatim) with in-memory TTL cache --------------------------

_geocode_cache: dict[str, tuple[float, dict | None]] = {}


async def _geocode(location: str) -> dict | None:
    """Resolve a human-readable location to coordinates via Nominatim.

    Results (including misses) are cached for GEOCODE_CACHE_TTL_S so the
    same location is never queried repeatedly within one conversation.
    """
    key = location.strip().lower()
    now = time.monotonic()
    cached = _geocode_cache.get(key)
    if cached and now - cached[0] < GEOCODE_CACHE_TTL_S:
        return cached[1]

    client = _get_client()
    for attempt in range(2):  # one bounded retry, Nominatim policy ~1 req/s
        try:
            resp = await client.get(
                NOMINATIM_URL,
                params={
                    "q": location,
                    "format": "json",
                    "limit": 1,
                    "accept-language": "en",
                },
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError(
                    f"Geocoder error {resp.status_code}",
                    request=resp.request,
                    response=resp,
                )
            resp.raise_for_status()
            results = resp.json()
            break
        except (httpx.HTTPError, ValueError):
            if attempt == 0:
                await asyncio.sleep(1.2)
            else:
                raise

    if not results:
        _geocode_cache[key] = (now, None)
        return None

    first = results[0]
    result = {
        "display_name": first.get("display_name") or location,
        "latitude": float(first["lat"]),
        "longitude": float(first["lon"]),
    }
    _geocode_cache[key] = (now, result)
    return result


# --- Overpass facility query with endpoint failover --------------------------


def _normalize_facility_type(raw: str) -> str | None:
    """Map free-form caller wording to a canonical facility type key."""
    if not raw:
        return None
    text = raw.strip().lower()
    for key in FACILITY_TYPE_TAGS:
        if key in text:
            return key
    return None


def _overpass_tags(facility_type: str | None) -> list[str]:
    if not facility_type:
        return DEFAULT_TAGS
    return FACILITY_TYPE_TAGS.get(facility_type, DEFAULT_TAGS)


def _tag_regex(facility_type: str | None) -> str:
    """Build the Overpass tag alternation, expanding 'doctors' with 'doctor'."""
    tags = set(_overpass_tags(facility_type))
    if "doctors" in tags:
        tags.add("doctor")
    return "|".join(sorted(tags))


async def _query_facilities(
    lat: float,
    lon: float,
    facility_type: str | None,
    radius_m: int = DEFAULT_RADIUS_M,
) -> list[dict]:
    """Query Overpass for health facilities, failing over across endpoints.

    Tries each public endpoint at most once (bounded), with a small delay
    between attempts. A successful response — even an empty one — stops the
    failover; only connection-level failures move on to the next endpoint.
    """
    tag_re = _tag_regex(facility_type)
    query = (
        f"[out:json][timeout:{int(HTTP_TIMEOUT_S) - 5}];"
        "("
        f'node["amenity"~"^({tag_re})$"]["name"](around:{radius_m},{lat},{lon});'
        f'way["amenity"~"^({tag_re})$"]["name"](around:{radius_m},{lat},{lon});'
        f'node["healthcare"~"^({tag_re})$"]["name"](around:{radius_m},{lat},{lon});'
        f'way["healthcare"~"^({tag_re})$"]["name"](around:{radius_m},{lat},{lon});'
        ");"
        f"out center {MAX_RESULTS * 3};"
    )

    client = _get_client()
    last_error: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = await client.post(endpoint, data={"data": query})
            resp.raise_for_status()
            data = resp.json()
            remark = data.get("remark")
            if remark and any(
                token in str(remark).lower()
                for token in ("runtime error", "rate_limited", "timed out", "error")
            ):
                raise OverpassQueryError(str(remark)[:200])
            elements = data.get("elements", [])
            if not isinstance(elements, list):
                elements = []
            return elements  # a valid (possibly empty) answer — stop failover
        except (httpx.HTTPError, ValueError, OverpassQueryError) as exc:
            last_error = exc
            logger.warning(
                "[HEALTH ACCESS] Overpass endpoint %s failed: %s", endpoint, exc
            )
            await asyncio.sleep(RETRY_DELAY_S)

    raise last_error if last_error else httpx.HTTPError("All Overpass endpoints failed")


# --- Parsing / validation ----------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres (approximate straight-line)."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return radius_km * 2 * math.asin(math.sqrt(a))


def _build_address(tags: dict) -> str:
    parts = []
    if tags.get("addr:housenumber"):
        parts.append(tags["addr:housenumber"])
    if tags.get("addr:street"):
        parts.append(tags["addr:street"])
    locality = (
        tags.get("addr:city")
        or tags.get("addr:town")
        or tags.get("addr:village")
        or tags.get("addr:district")
    )
    if locality:
        parts.append(locality)
    if tags.get("addr:state"):
        parts.append(tags["addr:state"])
    return ", ".join(parts)


def _element_to_facility(el: dict, lat: float, lon: float) -> dict | None:
    """Validate one OSM element into a facility. Returns None if malformed."""
    tags = el.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    if el.get("type") == "node":
        flat, flon = el.get("lat"), el.get("lon")
    else:
        center = el.get("center") or {}
        flat, flon = center.get("lat"), center.get("lon")
    if flat is None or flon is None:
        return None
    try:
        flat, flon = float(flat), float(flon)
    except (TypeError, ValueError):
        return None
    return {
        "name": name,
        "type": tags.get("amenity") or tags.get("healthcare") or "health facility",
        "address": _build_address(tags),
        "latitude": flat,
        "longitude": flon,
        "distance_km": round(_haversine_km(lat, lon, flat, flon), 2),
    }


# --- Tool result assembly ----------------------------------------------------


def _error_result(code: str, message: str) -> str:
    """Structured error result.

    Deliberately has NO `retrieved_at` — the agent must never claim data was
    retrieved after a failed lookup.
    """
    return json.dumps(
        {"status": "error", "code": code, "message": message}, ensure_ascii=False
    )


async def find_nearby_health_facilities_impl(
    location: str, facility_type: str = ""
) -> str:
    """Core implementation, kept separate from the LiveKit decorator for testability."""
    try:
        resolved = await _geocode(location)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("[HEALTH ACCESS] geocode failed for %r: %s", location, exc)
        return _error_result(
            "SERVICE_UNAVAILABLE",
            "The live health-facility lookup is temporarily unavailable. "
            "Tell the caller you cannot access the live lookup right now and do NOT "
            "want to give incorrect information; suggest trying again shortly or "
            "checking with a local healthcare provider. Do NOT invent any facility.",
        )

    if resolved is None:
        return _error_result(
            "LOCATION_NOT_FOUND",
            f"Could not identify the location '{location}'. "
            "Ask the caller for the city or district name.",
        )

    norm_type = _normalize_facility_type(facility_type)
    try:
        elements = await _query_facilities(
            resolved["latitude"], resolved["longitude"], norm_type
        )
    except (httpx.HTTPError, OverpassQueryError, ValueError) as exc:
        logger.warning(
            "[HEALTH ACCESS] facility query failed for %r: %s", location, exc
        )
        return _error_result(
            "SERVICE_UNAVAILABLE",
            "The live health-facility lookup is temporarily unavailable. "
            "Tell the caller you cannot access the live lookup right now and do NOT "
            "want to give incorrect information; suggest trying again shortly or "
            "checking with a local healthcare provider. Do NOT invent any facility.",
        )

    facilities = []
    for el in elements:
        facility = _element_to_facility(el, resolved["latitude"], resolved["longitude"])
        if facility:
            if not facility["address"]:
                # Never leave an empty address — fall back to the resolved area
                # (factual, from the geocoder) instead of inventing one.
                facility["address"] = resolved["display_name"]
            facilities.append(facility)
    facilities.sort(key=lambda f: f["distance_km"])
    facilities = facilities[:MAX_RESULTS]

    if not facilities:
        return _error_result(
            "NO_FACILITIES_FOUND",
            f"No health facilities were found near '{location}'. "
            "Tell the caller no matching facility was found for that location, and "
            "suggest trying a nearby town. Do NOT invent a facility.",
        )

    return json.dumps(
        {
            "status": "ok",
            "query": {"location": location, "facility_type": facility_type or "any"},
            "resolved_location": resolved["display_name"],
            "count": len(facilities),
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "distance_label": "approximate straight-line distance (km)",
            "source": "OpenStreetMap (Nominatim + Overpass API)",
            "facilities": facilities,
        },
        ensure_ascii=False,
    )


class HealthAccessTools:
    @function_tool
    async def find_nearby_health_facilities(
        self, context: RunContext, location: str, facility_type: str = ""
    ) -> str:
        """Find real, nearby health facilities (hospitals, clinics, health centres, PHCs, pharmacies) for a city or district.

        USE THIS TOOL WHEN the caller asks to LOCATE a health facility, for example:
        - "find a nearby hospital / clinic / health centre / PHC / pharmacy"
        - "where is the nearest health facility in Navsari?"
        - "can you find me a doctor near Surat?"
        - "where can I seek healthcare in <city/district>?"

        REQUIRED: a city, town, or district name in `location`. Use the location the
        caller provided — NEVER invent a location. If the caller has NOT given a
        location, do NOT call this tool; ask "Which city or district are you in?" first.

        DO NOT use this tool for diagnosis, treatment, symptoms, or emergencies — if
        the caller describes a medical emergency, escalate immediately instead of
        searching facilities.

        Args:
            location: The city, town, or district the caller is in (e.g. "Navsari", "Surat", "Vadodara").
            facility_type: Optional. One of "hospital", "clinic", "health centre", "phc", "pharmacy", "doctor". Empty string means any health facility.

        Returns JSON with real facilities (name, type, address, distance_km, source,
        retrieved_at — success only) or an explicit error (no timestamp, never invent
        a facility that is not in the result). Distances are approximate straight-line,
        not driving distances.
        """
        logger.info(
            "[HEALTH ACCESS] find_nearby_health_facilities location=%r facility_type=%r",
            location,
            facility_type,
        )
        return await find_nearby_health_facilities_impl(location, facility_type)
