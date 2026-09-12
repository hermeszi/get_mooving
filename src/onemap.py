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


def get_headers():
    if not ONEMAP_TOKEN:
        raise RuntimeError("ONEMAP_TOKEN is missing from .env")

    return {
        "Authorization": ONEMAP_TOKEN
    }

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

        response = requests.get(
            SEARCH_URL,
            headers=get_headers(),
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise RuntimeError(data["error"])

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

        response = requests.get(
            SEARCH_URL,
            headers=get_headers(),
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        data = response.json()

        if data.get("error"):
            raise RuntimeError(data["error"])

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

# def search_location(query: str) -> dict:
#     """
#     Convert an address/building name/postal code into coordinates.
#     """

#     params = {
#         "searchVal": query,
#         "returnGeom": "Y",
#         "getAddrDetails": "Y",
#         "pageNum": 1,
#     }

#     response = requests.get(
#         SEARCH_URL,
#         headers=get_headers(),
#         params=params,
#         timeout=10,
#     )

#     response.raise_for_status()

#     data = response.json()

#     if data.get("error"):
#         raise RuntimeError(data["error"])

#     results = data.get("results", [])

#     if not results:
#         raise ValueError(f"Location not found: {query}")

#     result = results[0]

#     return {
#         "address": result["ADDRESS"],
#         "latitude": float(result["LATITUDE"]),
#         "longitude": float(result["LONGITUDE"]),
#     }


def _request_route(params: dict) -> dict:
    response = requests.get(
        ROUTE_URL,
        headers=get_headers(),
        params=params,
        timeout=15,
    )

    response.raise_for_status()

    return response.json()


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

    raise RuntimeError(
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


def get_public_transport_time(
    start: dict,
    destination: dict,
    departure_time: datetime,
) -> int:
    """
    Return public-transport journey time in minutes.
    """

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