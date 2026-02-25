"""Generate archive/calendar.html: full-bleed square calendar grid from manifest + entry JSONs."""

from __future__ import annotations

import calendar
import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generator.entry_html import _load_manifest_full
from generator.index_html import _year_range_from_manifest
from generator.nav_context import tab_urls_for_root
from generator.text_to_html import get_first_photo_filename


def _build_calendar_data(
    manifest_path: Path,
    entries_dir: Path,
    import_dir: Path,
) -> dict:
    """
    Build calendar data: years with months, each month a 7-column grid of cells.
    Each cell: empty (pad), or {day, state: 'empty'|'entry'|'photo', single_url?, entries?, thumbnail_url?}.
    """
    manifest_full = _load_manifest_full(manifest_path)
    if not manifest_full:
        return {"weekdays": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], "years": []}

    entries_dir = Path(entries_dir)
    import_dir = Path(import_dir)

    # Group by date (YYYY-MM-DD); each date has list of (date_key, html_path, creation_date)
    by_date: dict[str, list[tuple[str, str, str]]] = {}
    for date_key, html_path, creation_date in manifest_full:
        date_part = date_key.split("_")[0]
        if len(date_part) < 10:
            continue
        by_date.setdefault(date_part, []).append((date_key, html_path, creation_date))

    # For each date, load entry JSONs and get first photo for first entry (by creation order)
    date_info: dict[str, dict] = {}  # date_part -> {state, single_url?, entries: [{url, label}], thumbnail_url?}
    for date_part, row_list in by_date.items():
        parts = date_part.split("-")
        year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("00", "00")
        entries_for_day: list[dict] = []
        thumbnail_url: str | None = None
        for date_key, html_path, creation_date in row_list:
            entry_url = f"entries/{html_path}"
            entry_json_path = entries_dir / year / month / f"{date_key}.json"
            label = "Entry"
            first_photo = None
            if entry_json_path.exists():
                with open(entry_json_path, encoding="utf-8") as f:
                    entry = json.load(f)
                creation = entry.get("creationDate", "")
                if creation:
                    try:
                        dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
                        s = dt.strftime("%I:%M %p")
                        label = s[1:] if len(s) > 0 and s[0] == "0" else s  # 3:06 PM not 03:06 PM
                    except (ValueError, TypeError):
                        label = creation[11:16] if len(creation) >= 16 else "Entry"
                photos_dir = entry_json_path.parent / "photos"
                first_photo = get_first_photo_filename(entry, import_dir, photos_dir)
                if first_photo and thumbnail_url is None:
                    thumbnail_url = f"entries/{year}/{month}/photos/{first_photo}"
            entries_for_day.append({"url": entry_url, "label": label})

        has_photo = thumbnail_url is not None
        date_info[date_part] = {
            "state": "photo" if has_photo else "entry",
            "single_url": entries_for_day[0]["url"] if len(entries_for_day) == 1 else None,
            "entries": entries_for_day,
            "thumbnail_url": thumbnail_url,
        }

    # Year range: include full years that have at least one entry
    years_with_entries: set[int] = set()
    for date_part in by_date:
        if len(date_part) >= 4:
            try:
                years_with_entries.add(int(date_part[:4]))
            except ValueError:
                pass
    if not years_with_entries:
        return {"weekdays": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"], "years": []}

    min_year = min(years_with_entries)
    max_year = max(years_with_entries)
    calendar.setfirstweekday(calendar.SUNDAY)

    years_data: list[dict] = []
    for year in range(min_year, max_year + 1):
        months_data: list[dict] = []
        for month in range(1, 13):
            first_weekday, ndays = calendar.monthrange(year, month)
            # first_weekday: 0=Monday in default; we set SUNDAY so 0=Sunday
            lead_empty = first_weekday  # number of cells before day 1
            cells: list[dict] = []
            for _ in range(lead_empty):
                cells.append({"empty": True})
            for day in range(1, ndays + 1):
                date_part = f"{year}-{month:02d}-{day:02d}"
                info = date_info.get(date_part)
                if not info:
                    cells.append({"day": day, "state": "empty", "empty": False})
                else:
                    entries = info.get("entries", [])
                    cells.append({
                        "day": day,
                        "state": info["state"],
                        "empty": False,
                        "single_url": info.get("single_url"),
                        "entries": entries,
                        "entries_json": json.dumps(entries) if entries else "[]",
                        "thumbnail_url": info.get("thumbnail_url"),
                    })
            months_data.append({
                "title": datetime(year, month, 1).strftime("%B %Y"),
                "year": year,
                "month": month,
                "cells": cells,
            })
        years_data.append({"year": year, "months": months_data})

    return {
        "weekdays": ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"],
        "years": years_data,
    }


def generate_calendar_html(
    import_dir: Path,
    archive_root: Path,
    entries_dir: Path,
    manifest_path: Path,
) -> None:
    """
    Generate archive/calendar.html: journal-by-date calendar with full-bleed square tiles,
    sticky weekday strip, and same shell as index (hero, compact header, tabs).
    """
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return

    calendar_data = _build_calendar_data(manifest_path, entries_dir, import_dir)
    year_range = _year_range_from_manifest(manifest_path)

    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("calendar.html")
    tab_urls = tab_urls_for_root()
    context = {
        "css_path": "assets/css/",
        "js_path": "assets/js/",
        "active_tab": "calendar",
        "tab_urls": tab_urls,
        "year_range": year_range,
        "weekdays": calendar_data["weekdays"],
        "years": calendar_data["years"],
        "photo_index_url": "entries/photo-index.json",
    }
    html = template.render(context)
    calendar_path = archive_root / "calendar.html"
    calendar_path.parent.mkdir(parents=True, exist_ok=True)
    calendar_path.write_text(html, encoding="utf-8")
