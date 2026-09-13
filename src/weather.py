"""
Looks up Singapore's NEA 2-hour weather forecast (free, public, no API
key) for a coordinate, matched to the nearest of NEA's 47 named areas.
Used to decide whether walking/cycling are worth suggesting.
"""

import requests

from onemap import straight_line_km


FORECAST_URL = "https://api.data.gov.sg/v1/environment/2-hour-weather-forecast"

RAIN_KEYWORDS = ("rain", "shower", "thundery")


def is_rainy(forecast_text: str) -> bool:
    text = forecast_text.lower()
    return any(keyword in text for keyword in RAIN_KEYWORDS)


def get_forecast(latitude: float, longitude: float) -> dict:
    """
    Return the nearest NEA 2-hour forecast area for a coordinate.
    """

    response = requests.get(FORECAST_URL, timeout=10)
    response.raise_for_status()

    data = response.json()

    areas = data["area_metadata"]
    forecasts = {
        entry["area"]: entry["forecast"]
        for entry in data["items"][0]["forecasts"]
    }

    point = {"latitude": latitude, "longitude": longitude}

    nearest = min(
        areas,
        key=lambda area: straight_line_km(point, area["label_location"]),
    )

    forecast_text = forecasts[nearest["name"]]

    return {
        "area": nearest["name"],
        "forecast": forecast_text,
        "rain": is_rainy(forecast_text),
    }


if __name__ == "__main__":
    forecast = get_forecast(1.375, 103.839)
    print(forecast)
