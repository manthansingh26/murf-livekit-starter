"""Day 5 unit tests — find_nearby_health_facilities (MOCKED, no network).

These tests exercise the REAL production code paths (`_geocode`, `_query_facilities`,
parsing, validation, failover, retries) by injecting `httpx.MockTransport` at the
HTTP layer. The separate live smoke test (`test_health_access_live.py`) covers the
real OpenStreetMap network behavior.
"""

import json

import httpx
import pytest

from tools import health_access as ha

NAVSARI = [
    {
        "display_name": "Navsari, Navsari Taluka, Navsari, Gujarat, 396400, India",
        "lat": "20.9504",
        "lon": "72.9222",
    }
]

FACILITIES = {
    "elements": [
        {
            "type": "node",
            "lat": 20.9504,
            "lon": 72.9222,
            "tags": {
                "name": "Navsari Civil Hospital",
                "amenity": "hospital",
                "addr:street": "Station Road",
                "addr:city": "Navsari",
                "addr:state": "Gujarat",
            },
        },
        {
            "type": "way",
            "center": {"lat": 20.9531, "lon": 72.9307},
            "tags": {"name": "City Clinic", "amenity": "clinic"},
        },
        {
            "type": "node",
            "lat": 20.9401,
            "lon": 72.9155,
            "tags": {"name": "Navsari Pharmacy", "amenity": "pharmacy"},
        },
    ]
}

EMPTY = {"elements": []}


def _route(
    nominatim_body=None, overpass_body=None, overpass_status=200, fail_overpass_hosts=()
):
    """Build an httpx.MockTransport handler that routes by host."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in request.url.host:
            return httpx.Response(200, json=nominatim_body or [], request=request)
        # Overpass request
        if request.url.host in fail_overpass_hosts:
            return httpx.Response(504, request=request)
        if overpass_status != 200:
            return httpx.Response(overpass_status, request=request)
        return httpx.Response(200, json=overpass_body or EMPTY, request=request)

    return handler


@pytest.fixture
async def mock_network():
    """Install a MockTransport; force client recreation; restore afterwards."""
    ha._client = None

    def install(handler):
        ha._test_transport = httpx.MockTransport(handler)
        ha._client = None
        ha._geocode_cache.clear()
        return ha._test_transport

    yield install

    ha._test_transport = None
    await ha._close_client()  # close the mocked client cleanly
    ha._geocode_cache.clear()


# ---------------------------------------------------------------------------
# 1. Success — real production path returns validated facilities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_success_returns_facilities(mock_network):
    mock_network(_route(nominatim_body=NAVSARI, overpass_body=FACILITIES))

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))

    assert out["status"] == "ok"
    assert out["count"] == 3
    assert out["query"]["location"] == "Navsari"
    assert out["source"] == "OpenStreetMap (Nominatim + Overpass API)"
    assert out["retrieved_at"]  # only success carries the timestamp
    assert out["distance_label"] == "approximate straight-line distance (km)"
    f0 = out["facilities"][0]
    assert f0["name"] == "Navsari Civil Hospital"
    assert f0["type"] == "hospital"
    assert f0["address"]  # built from addr: tags
    assert "latitude" in f0 and "longitude" in f0
    assert "distance_km" in f0
    # sorted by distance ascending
    dists = [f["distance_km"] for f in out["facilities"]]
    assert dists == sorted(dists)


@pytest.mark.asyncio
async def test_geocode_cache_prevents_repeat_nominatim_calls(mock_network):
    calls = {"nominatim": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in request.url.host:
            calls["nominatim"] += 1
            return httpx.Response(200, json=NAVSARI, request=request)
        return httpx.Response(200, json=FACILITIES, request=request)

    mock_network(handler)
    await ha.find_nearby_health_facilities_impl("Navsari")
    await ha.find_nearby_health_facilities_impl("Navsari")
    assert calls["nominatim"] == 1  # cached after first resolve


# ---------------------------------------------------------------------------
# 2. Unknown location
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_location(mock_network):
    mock_network(_route(nominatim_body=[]))

    out = json.loads(await ha.find_nearby_health_facilities_impl("Atlantis"))

    assert out["status"] == "error"
    assert out["code"] == "LOCATION_NOT_FOUND"
    assert "Atlantis" in out["message"]
    assert "facilities" not in out
    assert "retrieved_at" not in out  # failure must not imply retrieval


# ---------------------------------------------------------------------------
# 3. Timeouts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_geocode_timeout(mock_network):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    mock_network(handler)

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert out["code"] == "SERVICE_UNAVAILABLE"
    assert "facilities" not in out
    assert "retrieved_at" not in out


@pytest.mark.asyncio
async def test_overpass_all_endpoints_timeout(mock_network):
    """Geocode succeeds; every Overpass endpoint times out -> SERVICE_UNAVAILABLE."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in request.url.host:
            return httpx.Response(200, json=NAVSARI, request=request)
        raise httpx.ReadTimeout("timed out", request=request)

    mock_network(handler)

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert out["code"] == "SERVICE_UNAVAILABLE"
    assert "retrieved_at" not in out


# ---------------------------------------------------------------------------
# 4. HTTP failures: 429, 502/503/504, and failover across endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_429(mock_network):
    mock_network(_route(nominatim_body=NAVSARI, overpass_status=429))

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert out["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_http_502_503_504(mock_network):
    for status in (502, 503, 504):
        mock_network(_route(nominatim_body=NAVSARI, overpass_status=status))
        out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
        assert out["status"] == "error"
        assert out["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_failover_primary_down_secondary_works(mock_network):
    """Primary overpass-api.de returns 504; a mirror must be tried and succeed."""
    primary = ha.OVERPASS_ENDPOINTS[0]
    mock_network(
        _route(
            nominatim_body=NAVSARI,
            overpass_body=FACILITIES,
            fail_overpass_hosts=(primary.split("//")[1].split("/")[0],),
        )
    )

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "ok"
    assert out["count"] == 3


@pytest.mark.asyncio
async def test_overpass_remark_error_is_handled(mock_network):
    """Overpass can return 200 with a 'remark' error — must not fabricate."""

    def handler(request: httpx.Request) -> httpx.Response:
        if "nominatim" in request.url.host:
            return httpx.Response(200, json=NAVSARI, request=request)
        return httpx.Response(
            200, json={"remark": "runtime error: Query timed out"}, request=request
        )

    mock_network(handler)

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert out["code"] == "SERVICE_UNAVAILABLE"
    assert "facilities" not in out


# ---------------------------------------------------------------------------
# 5. Empty result / malformed elements — never fabricate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_facilities_found(mock_network):
    mock_network(_route(nominatim_body=NAVSARI, overpass_body=EMPTY))

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert out["code"] == "NO_FACILITIES_FOUND"
    assert "facilities" not in out
    assert "retrieved_at" not in out


@pytest.mark.asyncio
async def test_malformed_elements_skipped(mock_network):
    malformed = {
        "elements": [
            {
                "type": "node",
                "lat": 20.95,
                "lon": 72.92,
                "tags": {"amenity": "hospital"},
            },  # no name
            {
                "type": "way",
                "tags": {"name": "No Center", "amenity": "clinic"},
            },  # no center
            {
                "type": "node",
                "lat": "bad",
                "lon": "bad",
                "tags": {"name": "Bad Coords", "amenity": "clinic"},
            },
            {
                "type": "node",
                "lat": 20.9504,
                "lon": 72.9222,
                "tags": {"name": "Valid Hospital", "amenity": "hospital"},
            },
        ]
    }
    mock_network(_route(nominatim_body=NAVSARI, overpass_body=malformed))

    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "ok"
    assert out["count"] == 1
    assert out["facilities"][0]["name"] == "Valid Hospital"


@pytest.mark.asyncio
async def test_error_never_includes_retrieved_at(mock_network):
    """Regression: failures must not carry retrieved_at (no 'retrieved just now' claims)."""
    mock_network(_route(nominatim_body=NAVSARI, overpass_status=504))
    out = json.loads(await ha.find_nearby_health_facilities_impl("Navsari"))
    assert out["status"] == "error"
    assert "retrieved_at" not in out


# ---------------------------------------------------------------------------
# 6. Facility-type filtering + distance helpers
# ---------------------------------------------------------------------------


def test_normalize_facility_type():
    assert ha._normalize_facility_type("hospital") == "hospital"
    assert ha._normalize_facility_type("I need a nearby clinic") == "clinic"
    assert ha._normalize_facility_type("health centre") == "health centre"
    assert ha._normalize_facility_type("PHC") == "phc"
    assert ha._normalize_facility_type("pharmacy") == "pharmacy"
    assert ha._normalize_facility_type("doctor") == "doctor"
    assert ha._normalize_facility_type("") is None
    assert ha._normalize_facility_type(None) is None


def test_haversine_zero_distance():
    assert ha._haversine_km(20.95, 72.92, 20.95, 72.92) == 0


def test_haversine_known_distance():
    # Approx 1 km per 0.009 degrees of latitude
    d = ha._haversine_km(20.95, 72.92, 20.96, 72.92)
    assert 0.9 < d < 1.3


def test_element_to_facility_way_center():
    el = {
        "type": "way",
        "center": {"lat": 21.0, "lon": 73.0},
        "tags": {"name": "Test Clinic", "amenity": "clinic"},
    }
    f = ha._element_to_facility(el, 20.95, 72.92)
    assert f is not None
    assert f["name"] == "Test Clinic"
    assert f["distance_km"] > 0


def test_element_to_facility_missing_center():
    el = {"type": "way", "tags": {"name": "No Center", "amenity": "clinic"}}
    assert ha._element_to_facility(el, 20.95, 72.92) is None


def test_element_to_facility_bad_coords():
    el = {
        "type": "node",
        "lat": "abc",
        "lon": "def",
        "tags": {"name": "X", "amenity": "clinic"},
    }
    assert ha._element_to_facility(el, 20.95, 72.92) is None
