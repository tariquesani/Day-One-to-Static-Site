"""Extract entry metadata from Day One entry dicts for HTML generation."""

import re


def get_location(entry: dict) -> str:
    """Extract a human-readable location string from a Day One entry."""
    if "location" not in entry:
        return ""

    locations: list[str] = []
    for key in ["userLabel", "placeName", "localityName", "administrativeArea", "country"]:
        if key == "placeName" and "userLabel" in entry["location"]:
            continue
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
    parts: list[str] = []
    if "location" in entry and "localityName" in entry["location"]:
        parts.append(entry["location"]["localityName"])
    parts.append(f"{temp}°C {desc}")
    return " ".join(parts)


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
