#!/usr/bin/env python3
"""
Generates a daily weather + AQI .ics calendar feed using the free Open-Meteo API
(no API key required). Designed to be run once a day (e.g. via GitHub Actions
cron) to regenerate a static .ics file that people subscribe to via webcal://.

Usage:
    python3 generate_weather_ics.py --lat 40.4406 --lon -79.9959 \
        --name "Pittsburgh, PA" --out weather.ics
"""

import argparse
import sys
from datetime import datetime, timedelta, date, timezone
import requests
from icalendar import Calendar, Event
import uuid

# WMO weather codes -> human readable description
WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def aqi_category(aqi):
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def fetch_weather(lat, lon, days):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "weathercode",
            "windspeed_10m_max",
        ]),
        "temperature_unit": "fahrenheit",
        "windspeed_unit": "mph",
        "timezone": "auto",
        "forecast_days": days,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def fetch_aqi(lat, lon, days):
    url = "https://air-quality-api.open-meteo.com/v1/air-quality"
    # The air quality API only supports up to 7 forecast days, even when the
    # main weather forecast goes further out.
    aqi_days = min(days, 7)
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "us_aqi",
        "timezone": "auto",
        "forecast_days": aqi_days,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    # Aggregate hourly AQI into daily max (worst-case AQI is the standard way
    # to report a "daily AQI")
    daily_max = {}
    times = data.get("hourly", {}).get("time", [])
    values = data.get("hourly", {}).get("us_aqi", [])
    for t, v in zip(times, values):
        day = t.split("T")[0]
        if v is None:
            continue
        if day not in daily_max or v > daily_max[day]:
            daily_max[day] = v
    return daily_max


def build_calendar(lat, lon, place_name, days=10):
    weather = fetch_weather(lat, lon, days)
    aqi_by_day = fetch_aqi(lat, lon, days)

    cal = Calendar()
    cal.add("prodid", f"-//Daily Weather & AQI//{place_name}//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", f"Weather & AQI \u2014 {place_name}")
    cal.add("x-wr-timezone", weather.get("timezone", "UTC"))
    # Ask calendar clients to refresh at least once a day
    cal.add("x-published-ttl", "PT12H")

    daily = weather["daily"]
    dates = daily["time"]

    for i, day_str in enumerate(dates):
        d = datetime.strptime(day_str, "%Y-%m-%d").date()

        hi = daily["temperature_2m_max"][i]
        lo = daily["temperature_2m_min"][i]
        precip_pct = daily["precipitation_probability_max"][i]
        wind = daily["windspeed_10m_max"][i]
        code = daily["weathercode"][i]
        condition = WMO_CODES.get(code, "Unknown conditions")

        aqi = aqi_by_day.get(day_str)
        aqi_cat = aqi_category(aqi)

        summary = f"{place_name}: {condition}, {hi:.0f}\u00b0/{lo:.0f}\u00b0F"
        if aqi is not None:
            summary += f" \u2022 AQI {aqi:.0f} ({aqi_cat})"

        description_lines = [
            f"Conditions: {condition}",
            f"High: {hi:.0f}\u00b0F   Low: {lo:.0f}\u00b0F",
            f"Chance of precipitation: {precip_pct:.0f}%",
            f"Max wind: {wind:.0f} mph",
        ]
        if aqi is not None:
            description_lines.append(f"Air Quality Index (US AQI, daily max): {aqi:.0f} \u2014 {aqi_cat}")
        else:
            description_lines.append("Air Quality Index: not available for this day")

        event = Event()
        event.add("summary", summary)
        event.add("description", "\n".join(description_lines))
        event.add("dtstart", d)
        event.add("dtend", d + timedelta(days=1))
        event.add("dtstamp", datetime.now(timezone.utc))
        # Stable UID per date+place so re-generating updates the same event
        # instead of duplicating it in subscribers' calendars
        event.add("uid", f"{day_str}-{place_name.replace(' ', '-').replace(',', '')}@weather-aqi-ics")
        event.add("transp", "TRANSPARENT")  # doesn't block time as "busy"
        cal.add_component(event)

    return cal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lon", type=float, required=True)
    parser.add_argument("--name", type=str, required=True, help="Display name, e.g. 'Pittsburgh, PA'")
    parser.add_argument("--days", type=int, default=7, help="Number of forecast days (weather: up to 16, AQI capped at 7 by the API)")
    parser.add_argument("--out", type=str, default="weather.ics")
    args = parser.parse_args()

    cal = build_calendar(args.lat, args.lon, args.name, args.days)

    with open(args.out, "wb") as f:
        f.write(cal.to_ical())

    print(f"Wrote {args.out} with {args.days} days of events for {args.name}")


if __name__ == "__main__":
    main()
