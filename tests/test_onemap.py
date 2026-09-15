"""
onemap.py is a thin client for a real external API — these tests never
call it. Every network call goes through requests.get, mocked here, so
the suite runs offline and doesn't depend on a live (or expired)
ONEMAP_TOKEN. See DEVELOPMENT.md §52 for the real-token bugs this
mirrors: a missing token, an HTTP auth error, and OneMap's search
endpoint returning HTTP 200 with the error inside the JSON body
instead of raising a real 401.
"""

import requests
import pytest

import onemap
from onemap import (
    OneMapAuthError,
    OneMapUnavailableError,
    _extract_minutes,
    _same_point,
    search_location,
)


@pytest.fixture(autouse=True)
def fake_token(monkeypatch):
    # Independent of whatever's (or isn't) in the real .env — CI has
    # no .env at all, so without this every call would fail at
    # get_headers() before the mocked requests.get is ever reached.
    monkeypatch.setattr(onemap, "ONEMAP_TOKEN", "test-token")


def _response(status_code=200, json_data=None, http_error=False):
    response = requests.Response()
    response.status_code = status_code

    if http_error:
        error = requests.exceptions.HTTPError(f"HTTP {status_code}")
        error.response = response

        def raise_for_status():
            raise error

        response.raise_for_status = raise_for_status
    else:
        response.raise_for_status = lambda: None

    response.json = lambda: json_data or {}
    return response


# ---- _extract_minutes ----


def test_extract_minutes_from_itinerary():
    data = {"plan": {"itineraries": [{"duration": 2880}]}}  # 48 min exactly
    assert _extract_minutes(data) == 48


def test_extract_minutes_rounds_up():
    data = {"plan": {"itineraries": [{"duration": 61}]}}  # just over 1 min
    assert _extract_minutes(data) == 2


def test_extract_minutes_from_route_summary():
    data = {"route_summary": {"total_time": 1000}}
    assert _extract_minutes(data) == 17


def test_extract_minutes_malformed_response_raises():
    with pytest.raises(OneMapUnavailableError):
        _extract_minutes({"unexpected": "shape"})


# ---- _same_point ----


def test_same_point_true_for_identical_coordinates():
    a = {"latitude": 1.300, "longitude": 103.800}
    b = {"latitude": 1.300, "longitude": 103.800}
    assert _same_point(a, b) is True


def test_same_point_false_for_far_apart_coordinates():
    a = {"latitude": 1.300, "longitude": 103.800}
    b = {"latitude": 1.350, "longitude": 103.900}
    assert _same_point(a, b) is False


# ---- search_location ----


def test_search_location_postal_code_fallback(mocker):
    # Full address text finds nothing; the 6-digit postal code
    # embedded in it, tried second, does.
    empty = _response(json_data={"results": []})
    found = _response(json_data={
        "results": [{
            "ADDRESS": "8 SOMAPAH ROAD SINGAPORE 487372",
            "POSTAL": "487372",
            "LATITUDE": "1.34140",
            "LONGITUDE": "103.96350",
        }]
    })

    mock_get = mocker.patch("onemap.requests.get", side_effect=[empty, found])

    result = search_location("Messy building name near SUTD 487372")

    assert mock_get.call_count == 2
    assert result["postal"] == "487372"
    assert result["latitude"] == pytest.approx(1.34140)


def test_search_location_empty_results_raises_value_error(mocker):
    mocker.patch("onemap.requests.get", return_value=_response(json_data={"results": []}))

    with pytest.raises(ValueError):
        search_location("Nowhere at all")


def test_search_location_http_error_raises_unavailable(mocker):
    mocker.patch("onemap.requests.get", return_value=_response(status_code=500, http_error=True))

    with pytest.raises(OneMapUnavailableError):
        search_location("SUTD")


def test_search_location_http_401_raises_auth_error(mocker):
    mocker.patch("onemap.requests.get", return_value=_response(status_code=401, http_error=True))

    with pytest.raises(OneMapAuthError):
        search_location("SUTD")


def test_search_location_expired_token_in_200_body_raises_auth_error(mocker):
    # OneMap's search endpoint doesn't raise a 401 for an expired
    # token — it returns HTTP 200 with the error in the JSON body.
    mocker.patch(
        "onemap.requests.get",
        return_value=_response(status_code=200, json_data={
            "error": "Authentication token expired. Token is valid for 3 days."
        }),
    )

    with pytest.raises(OneMapAuthError):
        search_location("SUTD")


def test_search_location_missing_token_raises_auth_error(monkeypatch, mocker):
    monkeypatch.setattr(onemap, "ONEMAP_TOKEN", None)
    mock_get = mocker.patch("onemap.requests.get")

    with pytest.raises(OneMapAuthError):
        search_location("SUTD")

    mock_get.assert_not_called()


def test_search_location_network_error_raises_unavailable(mocker):
    mocker.patch(
        "onemap.requests.get",
        side_effect=requests.exceptions.ConnectionError("no route to host"),
    )

    with pytest.raises(OneMapUnavailableError):
        search_location("SUTD")
