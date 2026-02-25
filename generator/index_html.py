"""Generate archive index (list view) HTML for Day One entries."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader

from generator import entry_helpers
from generator.nav_context import tab_urls_for_root
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
            "snippet": entry_helpers.index_snippet(entry),
            "meta_line": entry_helpers.index_meta_line(entry),
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
    tab_urls = tab_urls_for_root()
    context = {
        "css_path": "assets/css/",
        "js_path": "assets/js/",
        "active_tab": "list",
        "tab_urls": tab_urls,
        "months": months_list,
        "year_range": _year_range_from_manifest(manifest_path),
        "photo_index_url": "entries/photo-index.json",
    }
    html = template.render(context)
    index_path = archive_root / "index.html"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(html, encoding="utf-8")

