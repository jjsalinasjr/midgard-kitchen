"""The narrative tool call — real live data wearing an Asgardian skin.

Design-plan §Story + D18. Thor "reads the skies" over a mortal city via the free,
no-key Open-Meteo API, then counsels a feast fit for the weather. This is the
take-home's "make a tool call that fits the narrative": a real external API call
that needs no extra account or key.

Networking note: forces IPv4 + retries. macOS's async DNS resolver
intermittently fails the IPv6/AAAA lookup with errno 8 even when the host is
reachable (curl, which does a synchronous IPv4 lookup, succeeds); pinning
AF_INET and retrying sidesteps that.
"""

from __future__ import annotations

import asyncio
import socket

import aiohttp

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather codes -> plain description (spoken by Thor).
_WEATHER = {
    0: "clear skies",
    1: "mostly clear skies",
    2: "partly cloudy skies",
    3: "grey, overcast skies",
    45: "thick fog",
    48: "freezing fog",
    51: "a light drizzle",
    53: "a steady drizzle",
    55: "a heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "freezing rain",
    67: "heavy freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "rain showers",
    81: "rain showers",
    82: "violent rain showers",
    85: "snow showers",
    86: "heavy snow showers",
    95: "a thunderstorm",
    96: "a thunderstorm with hail",
    99: "a fierce thunderstorm with hail",
}


async def _get_json(session: aiohttp.ClientSession, url: str, params: dict) -> dict:
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


async def read_the_skies(location: str, attempts: int = 3) -> str:
    """Look up the current weather over `location` and describe it in Thor's terms."""
    timeout = aiohttp.ClientTimeout(total=10)
    connector = aiohttp.TCPConnector(family=socket.AF_INET)  # force IPv4 (see module docstring)
    last_error: Exception | None = None

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for attempt in range(attempts):
            try:
                geo = await _get_json(session, _GEOCODE_URL, {"name": location, "count": 1})
                results = geo.get("results")
                if not results:
                    return f"The realm called '{location}' is hidden even from my sight — name another."

                place = results[0]
                where = ", ".join(x for x in (place.get("name"), place.get("country")) if x)

                wx = await _get_json(
                    session,
                    _FORECAST_URL,
                    {
                        "latitude": place["latitude"],
                        "longitude": place["longitude"],
                        "current": "temperature_2m,weather_code",
                    },
                )
                current = wx["current"]
                temp_c = round(current["temperature_2m"])
                temp_f = round(temp_c * 9 / 5 + 32)
                sky = _WEATHER.get(current["weather_code"], "strange and shifting weather")
                return f"Over {where}, the skies show {sky}, and it is {temp_c} degrees Celsius ({temp_f} Fahrenheit)."
            except aiohttp.ClientError as exc:
                last_error = exc
                if attempt < attempts - 1:
                    await asyncio.sleep(0.3 * (attempt + 1))

    raise last_error  # exhausted retries; the agent tool turns this into a graceful message
