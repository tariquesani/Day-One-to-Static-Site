"""Generate HTML pages for Day One entries using Jinja templates."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generator import entry_helpers
from generator.archive_paths import output_dir_for_date_key
from generator.text_to_html import entry_text_to_html, get_first_photo_filename


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
        "css_path": "../../../assets/css/",
    }


def _load_manifest(manifest_path: Path) -> list[tuple[str, str]]:
    """Load manifest and return list of (date_key, html_path)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    # Manifest format: [date_key, html_path, creation_date]
    return [(row[0], row[1]) for row in entries if len(row) >= 2]


def _load_manifest_full(manifest_path: Path) -> list[tuple[str, str, str]]:
    """Load manifest and return list of (date_key, html_path, creation_date)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    result = []
    for row in entries:
        if len(row) >= 3:
            result.append((row[0], row[1], row[2]))
        elif len(row) >= 2:
            result.append((row[0], row[1], row[0]))
    return result


def _year_range_from_manifest(manifest_path: Path) -> str:
    """Return 'YYYY – YYYY' from oldest to newest entry year, or '' if no entries."""
    manifest_full = _load_manifest_full(manifest_path)
    if not manifest_full:
        return ""
    years = []
    for date_key, _, _ in manifest_full:
        date_part = date_key.split("_")[0]
        if len(date_part) >= 4:
            try:
                years.append(int(date_part[:4]))
            except ValueError:
                pass
    if not years:
        return ""
    return f"{min(years)} – {max(years)}"


def _format_month_title(year_month: str) -> str:
    """Format YYYY-MM to 'February 2026'."""
    if not year_month or len(year_month) < 7:
        return year_month
    try:
        year, month = int(year_month[:4]), int(year_month[5:7])
        return datetime(year, month, 1).strftime("%B %Y")
    except (ValueError, TypeError):
        return year_month


def _index_snippet(entry: dict, max_len: int = 80) -> str:
    """
    Build a short snippet for the index from the first one or two
    non-empty, non-image lines of the entry text, up to max_len.
    Also strips simple Markdown-style backslash escapes so that
    sequences like '\\.' render as '.'.
    """

    def _unescape_markdown(s: str) -> str:
        # Unescape common Markdown backslash-escaped punctuation.
        return re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", s)

    text = _unescape_markdown((entry.get("text") or "").strip())
    if not text:
        # Fallback to title helper for entries without text.
        raw = entry_helpers.get_title(entry)
        if not raw:
            return ""
        raw = _unescape_markdown(raw.strip())
        if len(raw) <= max_len:
            return raw
        return raw[: max_len - 1].rstrip() + "…"

    # Collect the first few meaningful lines (similar to get_title logic).
    lines: list[str] = []
    for line in text.split("\n"):
        candidate = line.strip()
        if not candidate:
            continue
        # Skip pure image markdown lines.
        if re.match(r"!\[\]", candidate):
            continue
        # Strip markdown headers (e.g. "## Heading").
        if re.search(r"^#+\s*", candidate) and not candidate.startswith("# ["):
            candidate = re.sub(r"^#+\s*", "", candidate)
        if candidate:
            lines.append(candidate)
        if len(lines) >= 3:
            break

    if not lines:
        return ""

    # Combine the first one or two lines, then truncate to max_len.
    snippet = " ".join(lines[:2]).strip()

    # Special exception: normalize this specific place name spelling in snippets.
    # If the entry's placeName is "Sanis", show it as "SANI's" instead.
    loc = entry.get("location") or {}
    place_name = (loc.get("placeName") or "").strip()
    if place_name == "Sanis":
        snippet = snippet.replace("Sanis", "SANI's")

    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 1].rstrip() + "…"


def _index_meta_line(entry: dict) -> str:
    """Time · location · weather for index row."""
    parts = []
    creation = entry.get("creationDate", "")
    if creation:
        t = _format_creation_time(creation)
        if t:
            parts.append(t)
    loc = entry_helpers.get_location(entry)
    if loc:
        # Special exception: normalize this specific place name spelling.
        # If the placeName is "Sanis", show it as "SANI's" instead.
        if "Sanis" in loc:
            loc = loc.replace("Sanis", "SANI's")
        parts.append(loc)
    weather = entry_helpers.get_weather(entry)
    if weather:
        parts.append(weather)
    return " · ".join(parts)


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

    context = _template_context(entry, date_key, body_html, prev_url, next_url, index_url)

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
    generate_index_html(import_dir, archive_root, entries_dir, manifest_path)


def generate_index_html(
    import_dir: Path,
    archive_root: Path,
    entries_dir: Path,
    manifest_path: Path,
) -> None:
    """
    Generate archive/index.html: list view with hero/compact header, tabs,
    sticky month titles, and entry rows (snippet, metadata, optional thumbnail).
    """
    manifest_full = _load_manifest_full(manifest_path)
    if not manifest_full:
        return

    entries_dir = Path(entries_dir)
    import_dir = Path(import_dir)
    # Newest first for list display
    manifest_full = list(reversed(manifest_full))

    # Group by year-month (YYYY-MM)
    months_map: dict[str, list[dict]] = {}
    for date_key, html_path, _ in manifest_full:
        date_part = date_key.split("_")[0]
        if len(date_part) >= 7:
            year_month = date_part[:7]
        else:
            year_month = "0000-00"
        parts = date_part.split("-")
        year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
        entry_json_path = entries_dir / year / month / f"{date_key}.json"
        if not entry_json_path.exists():
            continue
        with open(entry_json_path, encoding="utf-8") as f:
            entry = json.load(f)
        # Photos dir is inferred from this entry's location (same as its html/json).
        photos_dir = entry_json_path.parent / "photos"
        first_photo = get_first_photo_filename(entry, import_dir, photos_dir)
        creation = entry.get("creationDate", "")
        try:
            dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            dow = dt.strftime("%a")
            day = dt.strftime("%d")
        except (ValueError, TypeError):
            dow = ""
            day = creation[:10] if creation else ""
        entry_url = f"entries/{html_path}"
        thumbnail_url = None
        if first_photo:
            thumbnail_url = f"entries/{year}/{month}/photos/{first_photo}"
        row = {
            "date_iso": creation[:10] if creation else "",
            "dow": dow,
            "day": day,
            "snippet": _index_snippet(entry),
            "meta_line": _index_meta_line(entry),
            "entry_url": entry_url,
            "thumbnail_url": thumbnail_url,
        }
        months_map.setdefault(year_month, []).append(row)

    months_list = [
        {"title": _format_month_title(ym), "entries": entries}
        for ym, entries in sorted(months_map.items(), reverse=True)
    ]

    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("list.html")
    context = {
        "css_path": "assets/css/",
        "active_tab": "list",
        "index_url": "index.html",
        "calendar_url": "calendar.html",
        "media_url": "media.html",
        "map_url": "map.html",
        "months": months_list,
        "year_range": _year_range_from_manifest(manifest_path),
    }
    html = template.render(context)
    index_path = archive_root / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")
