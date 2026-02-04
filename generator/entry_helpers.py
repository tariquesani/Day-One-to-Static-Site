"""Extract entry metadata from Day One entry dicts for HTML generation."""

import re


def get_location(entry: dict) -> str:
    """Extract a human-readable location string from a Day One entry."""
    if "location" not in entry:
        return ""

    locations: list[str] = []
    for key in ["userLabel", "placeName", "localityName", "administrativeArea", "country"]:
        if key in entry["location"]:
            locations.append(entry["location"][key])
    return ", ".join(locations)


def get_coordinates(entry: dict) -> str:
    """Extract latitude,longitude from a Day One entry location."""
    if "location" not in entry:
        return ""
    loc = entry["location"]
    if "latitude" not in loc or "longitude" not in loc:
        return ""
    return f"{loc['latitude']},{loc['longitude']}"


def get_location_with_geo(entry: dict) -> str:
    """Return location string, or [location](geo:lat,long) when coordinates exist."""
    location = get_location(entry)
    coordinates = get_coordinates(entry)
    if not coordinates:
        return location
    return f"[{location}](geo:{coordinates})"


def get_duration(media_entry: dict) -> str:
    """Format duration in seconds as HH:MM:SS for media entries."""
    duration_seconds = int(media_entry.get("duration", 0))
    hours, remainder = divmod(duration_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def get_weather(entry: dict) -> str:
    """Extract weather description from a Day One entry."""
    if "weather" not in entry:
        return ""

    we = entry["weather"]
    if "temperatureCelsius" not in we or "conditionsDescription" not in we:
        return ""

    temp = int(we["temperatureCelsius"])
    desc = we["conditionsDescription"]
    return f"{temp}°C {desc}"


def get_place_name(entry: dict) -> str:
    """Extract placeName from entry location."""
    if "location" not in entry or "placeName" not in entry["location"]:
        return ""
    name = entry["location"]["placeName"] or ""
    if name == "Sanis":
        return "SANI's"
    return name


def get_locality_name(entry: dict) -> str:
    """Extract localityName from entry location."""
    if "location" not in entry or "localityName" not in entry["location"]:
        return ""
    return entry["location"]["localityName"] or ""


def get_country(entry: dict) -> str:
    """Extract country from entry location."""
    if "location" not in entry or "country" not in entry["location"]:
        return ""
    return entry["location"]["country"]


# Weather code -> emoji (Day One weatherCode values)
WEATHER_EMOJI: dict[str, str] = {
    "clear": "☀️",
    "mostly-clear": "🌤️",
    "partly-cloudy": "⛅",
    "mostly-cloudy": "☁️",
    "cloudy": "☁️",
    "overcast": "☁️",
    "fog": "🌫️",
    "haze": "🌫️",
    "mist": "🌫️",
    "drizzle": "🌦️",
    "rain": "🌧️",
    "heavy-rain": "🌧️",
    "snow": "❄️",
    "sleet": "🌨️",
    "thunderstorm": "⛈️",
    "tornado": "🌪️",
    "hurricane": "🌀",
}

# Moon phase code -> emoji
MOON_EMOJI: dict[str, str] = {
    "new": "🌑",
    "waxing-crescent": "🌒",
    "first-quarter": "🌓",
    "waxing-gibbous": "🌔",
    "full": "🌕",
    "waning-gibbous": "🌖",
    "last-quarter": "🌗",
    "waning-crescent": "🌘",
}


def get_weather_emoji(entry: dict) -> str:
    """Return emoji for weather condition."""
    if "weather" not in entry or "weatherCode" not in entry["weather"]:
        return ""
    code = entry["weather"]["weatherCode"]
    return WEATHER_EMOJI.get(code, "🌡️")


def get_moon_emoji(entry: dict) -> str:
    """Return emoji for moon phase."""
    if "weather" not in entry or "moonPhaseCode" not in entry["weather"]:
        return ""
    code = entry["weather"]["moonPhaseCode"]
    return MOON_EMOJI.get(code, "🌙")


def format_moon_phase(entry: dict) -> str:
    """Format moon phase code for display (e.g. waning-gibbous → Waning Gibbous)."""
    if "weather" not in entry or "moonPhaseCode" not in entry["weather"]:
        return ""
    code = entry["weather"]["moonPhaseCode"]
    if not code:
        return ""
    return code.replace("-", " ").title()


def get_tags(
    entry: dict,
    *,
    additional_tags: list[str] | None = None,
    tag_prefix: str = "",
) -> str:
    """Extract tags as a comma-separated string. Includes starred if applicable."""
    tag_list: list[str] = list(additional_tags or [])

    if "tags" in entry:
        for t in entry["tags"]:
            if not t:
                continue
            normalized = t.replace(" ", "-").replace("---", "-")
            tag_list.append(f"{tag_prefix}{normalized}")
        if entry.get("starred"):
            tag_list.append(f"{tag_prefix}starred")

    return ", ".join(tag_list) if tag_list else ""


def get_title(entry: dict, *, default_title: str = "") -> str:
    """
    Extract a sanitized title from the first non-image line of entry text.
    Non-interactive; does not mutate the entry.
    """
    if "text" not in entry or not entry["text"]:
        return default_title

    lines = entry["text"].strip().split("\n")
    entry_title: str | None = None

    for line in lines:
        if line and not re.match(r"!\[\]", line):
            entry_title = line
            break

    if not entry_title:
        return default_title

    # Strip markdown headers
    if re.search(r"^#+\s*", entry_title.strip()) and not entry_title.strip().startswith("# ["):
        entry_title = re.sub(r"^#+\s*", "", entry_title.strip())

    # Sanitize for filename/display: remove disallowed characters
    sanitized = re.sub(r'[\\/:\*?"<>|#^\[\]]', " ", entry_title).strip()
    return sanitized[:255] if sanitized else default_title
