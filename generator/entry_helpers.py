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


def index_snippet(entry: dict, max_len: int = 160) -> str:
    """
    Build a short snippet for the index/map from the first few
    non-empty, non-image lines of the entry text, up to max_len.
    Also strips simple Markdown-style backslash escapes so that
    sequences like '\\.' render as '.'.
    """
    def _unescape_markdown(s: str) -> str:
        return re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", s)

    text = _unescape_markdown((entry.get("text") or "").strip())
    if not text:
        raw = get_title(entry)
        if not raw:
            return ""
        raw = _unescape_markdown(raw.strip())
        if len(raw) <= max_len:
            return raw
        return raw[: max_len - 1].rstrip() + "…"

    lines: list[str] = []
    for line in text.split("\n"):
        candidate = line.strip()
        if not candidate:
            continue
        if re.match(r"!\[\]", candidate):
            continue
        if re.search(r"^#+\s*", candidate) and not candidate.startswith("# ["):
            candidate = re.sub(r"^#+\s*", "", candidate)
        if candidate:
            lines.append(candidate)
        if len(lines) >= 3:
            break

    if not lines:
        return ""

    snippet = " ".join(lines[:3]).strip()
    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 1].rstrip() + "…"


def index_meta_line(entry: dict) -> str:
    """Time · location · weather for index row."""
    from datetime import datetime

    parts: list[str] = []
    creation = entry.get("creationDate", "")
    if creation:
        try:
            dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            hour = dt.hour % 12 or 12
            t = f"{hour}:{dt.minute:02d} {dt.strftime('%p')}"
        except (ValueError, TypeError):
            t = ""
        if t:
            parts.append(t)
    loc = get_location(entry)
    if loc:
        parts.append(loc)
    weather = get_weather(entry)
    if weather:
        parts.append(weather)
    return " · ".join(parts)


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
