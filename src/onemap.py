"""
Thin client for Singapore's OneMap API: geocoding/POI search
(search_location, search_places) and travel-time routing across
public transport, drive, walk, and cycle. Needs ONEMAP_TOKEN in .env —
OneMap tokens expire roughly every 3 days and must be refreshed
manually (see SETUP.md).

Every network call goes through _get(), which turns a missing token,
an auth failure, or any other OneMap/network error into one of the
two exceptions below — never a bare requests exception or RuntimeError
leaking out. Every caller is expected to catch OneMapError (or its two
subclasses) alongside the existing "not found" ValueError, so a
script's --json output stays a clean {"error", "message"} object no
matter what actually went wrong.
"""

import os
import math
import requests
import re

from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

ONEMAP_TOKEN = os.getenv("ONEMAP_TOKEN")

SEARCH_URL = "https://www.onemap.gov.sg/api/common/elastic/search"
ROUTE_URL = "https://www.onemap.gov.sg/api/public/routingsvc/route"


class OneMapError(Exception):
    """Any OneMap failure that isn't a plain 'location not found'."""


class OneMapAuthError(OneMapError):
    """Missing, invalid, or expired ONEMAP_TOKEN."""


class OneMapUnavailableError(OneMapError):
    """Network/timeout/server-side failure — not an auth problem."""


def onemap_error_reason(error: OneMapError) -> str:
    """
    Machine-readable error code for a caught OneMapError, for a
    script's --json "error" field. Shared so every caller classifies
    the same way instead of re-implementing the isinstance check.
    """
    return "onemap_auth_failed" if isinstance(error, OneMapAuthError) else "onemap_unavailable"


def get_headers():
    if not ONEMAP_TOKEN:
        raise OneMapAuthError("ONEMAP_TOKEN is missing from .env")

    return {
        "Authorization": ONEMAP_TOKEN
    }


def _get(url: str, params: dict, timeout: int) -> dict:
    """
    Shared request path for both OneMap endpoints. Converts a missing
    token, an HTTP auth error, any other HTTP error, or a network
    failure into OneMapAuthError/OneMapUnavailableError, so nothing
    above this function ever sees a raw requests exception.
    """

    try:
        response = requests.get(
            url,
            headers=get_headers(),
            params=params,
            timeout=timeout,
        )

        response.raise_for_status()

    except OneMapError:
        raise

    except requests.exceptions.HTTPError as error:
        status = error.response.status_code if error.response is not None else None

        if status in (401, 403):
            raise OneMapAuthError(
                f"OneMap authentication failed (HTTP {status}). "
                "Refresh ONEMAP_TOKEN — it expires roughly every 3 days."
            ) from error

        raise OneMapUnavailableError(f"OneMap returned HTTP {status}.") from error

    except requests.exceptions.RequestException as error:
        raise OneMapUnavailableError(f"Could not reach OneMap: {error}") from error

    return response.json()


# OneMap's search endpoint returns HTTP 200 with the error described in
# the JSON body for an expired/invalid token — confirmed live, it does
# not raise a 401 the way the routing endpoint does. Classify these by
# message content so both endpoints surface the same OneMapAuthError.
_AUTH_ERROR_KEYWORDS = ("token", "auth", "unauthorized", "unauthorised")


def _raise_for_data_error(message: str):
    if any(keyword in message.lower() for keyword in _AUTH_ERROR_KEYWORDS):
        raise OneMapAuthError(f"OneMap authentication failed: {message}")

    raise OneMapUnavailableError(message)


def search_location(query: str) -> dict:
    """
    Convert an address/building name/postal code into coordinates.

    Try the full query first.
    If that fails, try a Singapore 6-digit postal code found in the text.
    """

    queries = [query]

    # Find Singapore postal code, e.g. 308232
    postal_match = re.search(r"\b\d{6}\b", query)

    if postal_match:
        postal_code = postal_match.group()

        if postal_code not in queries:
            queries.append(postal_code)

    for search_query in queries:

        params = {
            "searchVal": search_query,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": 1,
        }

        data = _get(SEARCH_URL, params, timeout=10)

        if data.get("error"):
            _raise_for_data_error(data["error"])

        results = data.get("results", [])

        if results:
            result = results[0]

            return {
                "address": result["ADDRESS"],
                "postal": result.get("POSTAL"),
                "latitude": float(result["LATITUDE"]),
                "longitude": float(result["LONGITUDE"]),
            }

    raise ValueError(f"Location not found: {query}")


def search_places(query: str, near: dict, limit: int = 3) -> list:
    """
    Find named places/branches matching a brand or place name (e.g.
    "McDonald's"), sorted by straight-line distance to `near`.

    Unlike search_location(), this returns multiple candidates instead
    of assuming the first result is correct — a fuzzy brand name can
    match several real branches, or an unrelated building with a
    similar name.
    """

    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = {
            "searchVal": query,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": page,
        }

        data = _get(SEARCH_URL, params, timeout=10)

        if data.get("error"):
            _raise_for_data_error(data["error"])

        results.extend(data.get("results", []))
        total_pages = data.get("totalNumPages", 1)
        page += 1

    if not results:
        raise ValueError(f"Location not found: {query}")

    candidates = [
        {
            "name": result.get("SEARCHVAL") or result["ADDRESS"],
            "address": result["ADDRESS"],
            "postal": result.get("POSTAL"),
            "latitude": float(result["LATITUDE"]),
            "longitude": float(result["LONGITUDE"]),
        }
        for result in results
    ]

    candidates.sort(key=lambda candidate: straight_line_km(near, candidate))

    for candidate in candidates:
        candidate["distance_km"] = round(straight_line_km(near, candidate), 2)

    return candidates[:limit]


def _request_route(params: dict) -> dict:
    return _get(ROUTE_URL, params, timeout=15)


def _extract_minutes(data: dict) -> int:
    # OneMap PT responses normally contain itineraries.
    itineraries = data.get("plan", {}).get("itineraries", [])

    if itineraries:
        seconds = itineraries[0]["duration"]
        return math.ceil(seconds / 60)

    # walk/drive/cycle responses use route_summary instead.
    route_summary = data.get("route_summary")

    if route_summary and "total_time" in route_summary:
        return math.ceil(route_summary["total_time"] / 60)

    raise OneMapUnavailableError(
        f"Could not find journey duration in OneMap response: {data}"
    )


def _start_end_params(start: dict, destination: dict) -> dict:
    return {
        "start": f"{start['latitude']},{start['longitude']}",
        "end": (
            f"{destination['latitude']},"
            f"{destination['longitude']}"
        ),
    }


def _same_point(a: dict, b: dict, threshold_km: float = 0.05) -> bool:
    """
    OneMap's routing endpoint 404s on a same-point request (e.g. an
    event whose location is the user's own starting address) instead
    of returning a real "0 minutes" answer. Checked before calling it
    at all, using coordinates already on hand — no extra API call.
    """

    return straight_line_km(a, b) < threshold_km


def get_public_transport_time(
    start: dict,
    destination: dict,
    departure_time: datetime,
) -> int:
    """
    Return public-transport journey time in minutes.
    """

    if _same_point(start, destination):
        return 0

    params = {
        **_start_end_params(start, destination),
        "routeType": "pt",
        "mode": "TRANSIT",
        "date": departure_time.strftime("%m-%d-%Y"),
        "time": departure_time.strftime("%H:%M:%S"),
        "maxWalkDistance": 1000,
        "numItineraries": 1,
    }

    return _extract_minutes(_request_route(params))


def get_drive_time(
    start: dict,
    destination: dict,
    departure_time: datetime,
) -> int:
    """
    Return driving (car/taxi) journey time in minutes.
    """

    if _same_point(start, destination):
        return 0

    params = {
        **_start_end_params(start, destination),
        "routeType": "drive",
        "date": departure_time.strftime("%m-%d-%Y"),
        "time": departure_time.strftime("%H:%M:%S"),
    }

    return _extract_minutes(_request_route(params))


def get_walk_time(
    start: dict,
    destination: dict,
    departure_time: datetime,
) -> int:
    """
    Return walking journey time in minutes.
    """

    if _same_point(start, destination):
        return 0

    params = {
        **_start_end_params(start, destination),
        "routeType": "walk",
        "date": departure_time.strftime("%m-%d-%Y"),
        "time": departure_time.strftime("%H:%M:%S"),
    }

    return _extract_minutes(_request_route(params))


def get_cycle_time(
    start: dict,
    destination: dict,
    departure_time: datetime,
) -> int:
    """
    Return cycling journey time in minutes.
    """

    if _same_point(start, destination):
        return 0

    params = {
        **_start_end_params(start, destination),
        "routeType": "cycle",
        "date": departure_time.strftime("%m-%d-%Y"),
        "time": departure_time.strftime("%H:%M:%S"),
    }

    return _extract_minutes(_request_route(params))


def straight_line_km(a: dict, b: dict) -> float:
    """
    Straight-line ("as the crow flies") distance in km between two
    {latitude, longitude} points. Used to decide whether a route is
    even worth asking about for walking/cycling, before making a
    routing call.
    """

    lat1, lon1 = math.radians(a["latitude"]), math.radians(a["longitude"])
    lat2, lon2 = math.radians(b["latitude"]), math.radians(b["longitude"])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )

    earth_radius_km = 6371
    return 2 * earth_radius_km * math.asin(math.sqrt(h))


if __name__ == "__main__":
    start = search_location("SUTD")

    destination = search_location("308232")

    print("START:")
    print(start)

    print("\nDESTINATION:")
    print(destination)

    departure = datetime.fromisoformat(
        "2026-09-11T13:30:00+08:00"
    )

    minutes = get_public_transport_time(
        start,
        destination,
        departure,
    )

    print()
    print(f"🚇 Estimated journey: {minutes} minutes")