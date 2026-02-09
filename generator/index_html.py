"""Generate archive index (list view) HTML for Day One entries."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from generator import entry_helpers
from generator.text_to_html import get_first_photo_filename


def _load_manifest_full(manifest_path: Path) -> list[tuple[str, str, str]]:
    """Load manifest and return list of (date_key, html_path, creation_date)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    result: list[tuple[str, str, str]] = []
    for row in entries:
        if len(row) >= 4:
            result.append((row[1], row[2], row[3]))
        elif len(row) >= 3:
            result.append((row[0], row[1], row[2]))
        elif len(row) >= 2:
            result.append((row[0], row[1], row[0]))
    return result


def _year_range_from_manifest(manifest_path: Path) -> str:
    """Return 'YYYY – YYYY' from oldest to newest entry year, or '' if no entries."""
    manifest_full = _load_manifest_full(manifest_path)
    if not manifest_full:
        return ""
    years: list[int] = []
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
    import re

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

    if len(snippet) <= max_len:
        return snippet
    return snippet[: max_len - 1].rstrip() + "…"


def _index_meta_line(entry: dict) -> str:
    """Time · location · weather for index row."""
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
    loc = entry_helpers.get_location(entry)
    if loc:
        parts.append(loc)
    weather = entry_helpers.get_weather(entry)
    if weather:
        parts.append(weather)
    return " · ".join(parts)


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
        dow = ""
        day = ""
        date_iso = ""
        if creation:
            tz_name = ((entry.get("location") or {}).get("timeZoneName") or entry.get("timeZone"))
            try:
                dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
                # Treat stored creationDate as UTC, then convert to entry's timezone if known.
                try:
                    dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                    if tz_name:
                        dt = dt.astimezone(ZoneInfo(tz_name))
                except Exception:
                    # If timezone lookup fails, fall back to naive/UTC interpretation.
                    pass
                dow = dt.strftime("%a")
                day = dt.strftime("%d")
                date_iso = dt.strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                day = creation[:10] if creation else ""
                date_iso = creation[:10] if creation else ""
        row_date_iso = date_iso or (creation[:10] if creation else "")
        entry_url = f"entries/{html_path}"
        thumbnail_url = None
        if first_photo:
            thumbnail_url = f"entries/{year}/{month}/photos/{first_photo}"
        row = {
            "date_iso": row_date_iso,
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

