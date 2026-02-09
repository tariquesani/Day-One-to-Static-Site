"""Generate per-entry HTML pages for Day One entries using Jinja templates."""

import json
import os
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generator import entry_helpers
from generator.archive_paths import output_dir_for_date_key
from generator.text_to_html import entry_text_to_html


def _format_creation_date(iso_date: str) -> str:
    """Format ISO date for display (e.g. Sat, 31 Jan 2026)."""
    if not iso_date:
        return ""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%a, %d %b %Y")
    except (ValueError, TypeError):
        return iso_date[:10] if iso_date else ""


def _format_creation_time(iso_date: str) -> str:
    """Format ISO date time for display in entry timezone (e.g. 5:53 AM)."""
    if not iso_date:
        return ""
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        hour = dt.hour % 12 or 12
        return f"{hour}:{dt.minute:02d} {dt.strftime('%p')}"
    except (ValueError, TypeError):
        return ""


def _template_context(
    entry: dict,
    date_key: str,
    body_html: str,
    prev_url: str | None,
    next_url: str | None,
    index_url: str,
    calendar_url: str,
    media_url: str,
    map_url: str,
) -> dict:
    """Build the Jinja template context for an entry."""
    creation_date = entry.get("creationDate", "")
    title_raw = entry_helpers.get_title(entry)
    title = f"{title_raw} · Journal" if title_raw else _format_creation_date(creation_date) + " · Journal"

    loc = entry.get("location", {})
    latitude = str(loc["latitude"]) if "latitude" in loc else ""
    longitude = str(loc["longitude"]) if "longitude" in loc else ""

    return {
        "title": title,
        "creation_date_iso": creation_date,
        "creation_date_formatted": _format_creation_date(creation_date),
        "creation_time_formatted": _format_creation_time(creation_date),
        "location": entry_helpers.get_location(entry),
        "place_name": entry_helpers.get_place_name(entry),
        "locality_name": entry_helpers.get_locality_name(entry),
        "country": entry_helpers.get_country(entry),
        "latitude": latitude,
        "longitude": longitude,
        "body_html": body_html,
        "weather": entry_helpers.get_weather(entry),
        "weather_emoji": entry_helpers.get_weather_emoji(entry),
        "moon_phase": entry_helpers.format_moon_phase(entry),
        "moon_emoji": entry_helpers.get_moon_emoji(entry),
        "prev_url": prev_url,
        "next_url": next_url,
        "index_url": index_url,
        "calendar_url": calendar_url,
        "media_url": media_url,
        "map_url": map_url,
        "css_path": "../../../assets/css/",
    }


def _load_manifest(manifest_path: Path) -> list[tuple[str, str]]:
    """Load manifest and return list of (date_key, html_path)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    # Manifest format: [uuid, date_key, html_path, creation_date] or legacy [date_key, html_path, creation_date]
    result = []
    for row in entries:
        if len(row) >= 4:
            result.append((row[1], row[2]))
        elif len(row) >= 2:
            result.append((row[0], row[1]))
    return result


def _load_manifest_full(manifest_path: Path) -> list[tuple[str, str, str]]:
    """Load manifest and return list of (date_key, html_path, creation_date)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    result = []
    for row in entries:
        if len(row) >= 4:
            result.append((row[1], row[2], row[3]))
        elif len(row) >= 3:
            result.append((row[0], row[1], row[2]))
        elif len(row) >= 2:
            result.append((row[0], row[1], row[0]))
    return result


def _prev_next_urls(
    date_key: str,
    manifest_entries: list[tuple[str, str]],
    current_output_dir: Path,
    entries_dir: Path,
) -> tuple[str | None, str | None]:
    """Return (prev_url, next_url) as paths relative to current entry."""
    for i, (dk, html_path) in enumerate(manifest_entries):
        if dk == date_key:
            prev_path = manifest_entries[i - 1][1] if i > 0 else None
            next_path = manifest_entries[i + 1][1] if i + 1 < len(manifest_entries) else None
            prev_url = None
            next_url = None
            if prev_path:
                target = entries_dir / prev_path
                prev_url = os.path.relpath(target, current_output_dir).replace("\\", "/")
            if next_path:
                target = entries_dir / next_path
                next_url = os.path.relpath(target, current_output_dir).replace("\\", "/")
            return (prev_url, next_url)
    return (None, None)


def generate_entry_html(
    entry_json_path: Path,
    date_key: str,
    import_dir: Path,
    entries_dir: Path,
    manifest_path: Path,
) -> None:
    """
    Generate an HTML file for a single entry.
    Copies photos to entries/YYYY/MM/photos/ and renders the template.
    """
    entries_dir = Path(entries_dir)
    output_dir = output_dir_for_date_key(entries_dir, date_key)
    photos_dir = output_dir / "photos"

    with open(entry_json_path, encoding="utf-8") as f:
        entry = json.load(f)

    body_html = entry_text_to_html(entry, import_dir, photos_dir)

    manifest_entries = _load_manifest(manifest_path)
    prev_url, next_url = _prev_next_urls(date_key, manifest_entries, output_dir, entries_dir)
    archive_root = entries_dir.parent
    index_url = os.path.relpath(archive_root / "index.html", output_dir).replace("\\", "/")
    calendar_url = os.path.relpath(archive_root / "calendar.html", output_dir).replace("\\", "/")
    media_url = os.path.relpath(archive_root / "media.html", output_dir).replace("\\", "/")
    map_url = os.path.relpath(archive_root / "map.html", output_dir).replace("\\", "/")

    context = _template_context(entry, date_key, body_html, prev_url, next_url, index_url, calendar_url, media_url, map_url)

    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("entry.html")
    html = template.render(context)

    output_path = output_dir / f"{date_key}.html"
    output_path.write_text(html, encoding="utf-8")


def generate_all_entry_html(
    import_dir: Path,
    entries_dir: Path,
    manifest_path: Path,
) -> None:
    """
    Generate HTML for all entries in the manifest.
    Entry JSONs must already exist in entries_dir.
    """
    entries_dir = Path(entries_dir)
    manifest_path = Path(manifest_path)
    manifest_entries = _load_manifest(manifest_path)

    for date_key, _ in manifest_entries:
        date_part = date_key.split("_")[0]
        parts = date_part.split("-")
        year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
        entry_json_path = entries_dir / year / month / f"{date_key}.json"

        if entry_json_path.exists():
            generate_entry_html(
                entry_json_path,
                date_key,
                import_dir,
                entries_dir,
                manifest_path,
            )

    archive_root = entries_dir.parent
    # The index page generation now lives in generator/index_html.py
