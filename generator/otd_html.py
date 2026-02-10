"""Generate On This Day (OTD) pages: one per calendar day (MM-DD), all 366 days."""

import json
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generator import entry_helpers
from generator.archive_paths import output_dir_for_date_key
from generator.entry_html import _format_creation_date, _format_creation_time
from generator.text_to_html import entry_text_to_html


# All calendar days in order (01-01 through 12-31, including 02-29) for prev/next wrap.
def _all_mm_dd() -> list[str]:
    days = []
    for month in range(1, 13):
        max_day = 31
        if month in (4, 6, 9, 11):
            max_day = 30
        elif month == 2:
            max_day = 29
        for day in range(1, max_day + 1):
            days.append(f"{month:02d}-{day:02d}")
    return days


ALL_MM_DD = _all_mm_dd()


def _scan_entries_by_mm_dd(entries_dir: Path) -> dict[str, list[tuple[str, str, Path]]]:
    """
    Scan entries_dir for *.json (excluding on-this-day), return map:
    MM-DD -> [(year, date_key, json_path), ...] (unsorted).
    """
    result: dict[str, list[tuple[str, str, Path]]] = {}
    for json_path in entries_dir.rglob("*.json"):
        try:
            # Skip on-this-day folder
            parts = json_path.relative_to(entries_dir).parts
            if "on-this-day" in parts:
                continue
            if len(parts) < 3:
                continue
            year, month, filename = parts[0], parts[1], json_path.stem
            date_part = filename.split("_")[0]
            if len(date_part) != 10 or date_part[4] != "-" or date_part[7] != "-":
                continue
            mm_dd = date_part[5:]  # MM-DD
            if mm_dd not in result:
                result[mm_dd] = []
            result[mm_dd].append((year, filename, json_path))
        except (ValueError, IndexError):
            continue
    return result


def _body_html_for_otd(
    entry: dict,
    entry_output_dir: Path,
    photo_src_prefix: str,
) -> str:
    """
    Return body HTML for an entry as shown on an OTD page.
    Uses entry's existing photos dir; rewrites img src to be relative to OTD page.
    """
    photos_dir = entry_output_dir / "photos"
    # Use entry's output dir as import_dir so photos are found there (no original zip needed)
    html = entry_text_to_html(entry, entry_output_dir, photos_dir)
    # Rewrite photos/... to ../../YYYY/MM/photos/... relative to on-this-day/
    html = re.sub(r'src="photos/', f'src="{photo_src_prefix}photos/', html)
    return html


def _entry_context_for_otd(
    entry: dict,
    entry_output_dir: Path,
    photo_src_prefix: str,
) -> dict:
    """Build per-entry context for OTD template (same fields as entry template)."""
    creation_date = entry.get("creationDate", "")
    loc = entry.get("location", {})
    latitude = str(loc["latitude"]) if "latitude" in loc else ""
    longitude = str(loc["longitude"]) if "longitude" in loc else ""
    body_html = _body_html_for_otd(entry, entry_output_dir, photo_src_prefix)
    return {
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
    }


def _format_otd_label_windows(mm_dd: str) -> str:
    """Format MM-DD as 'February 10' (Windows doesn't support %-d)."""
    try:
        month_num = int(mm_dd[:2], 10)
        day_num = int(mm_dd[3:5], 10)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        return f"{months[month_num - 1]} {day_num}"
    except (ValueError, TypeError, IndexError):
        return mm_dd


def generate_otd_pages(entries_dir: Path) -> None:
    """
    Generate one HTML page per calendar day under entries/on-this-day/ (366 pages).
    Entries are grouped by year (newest first), ordered by creationDate desc within year.
    Prev/next link to adjacent calendar days with wrap. No index.html.
    """
    entries_dir = Path(entries_dir)
    otd_dir = entries_dir / "on-this-day"
    otd_dir.mkdir(parents=True, exist_ok=True)

    by_mm_dd = _scan_entries_by_mm_dd(entries_dir)
    n = len(ALL_MM_DD)
    archive_root = entries_dir.parent
    css_path = "../../assets/css/"

    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("on_this_day.html")

    for i, mm_dd in enumerate(ALL_MM_DD):
        prev_mm_dd = ALL_MM_DD[(i - 1) % n]
        next_mm_dd = ALL_MM_DD[(i + 1) % n]
        prev_url = f"{prev_mm_dd}.html"
        next_url = f"{next_mm_dd}.html"
        prev_label = _format_otd_label_windows(prev_mm_dd)
        next_label = _format_otd_label_windows(next_mm_dd)

        day_label = _format_otd_label_windows(mm_dd)
        title = f"On {day_label} · Journal"

        rows = by_mm_dd.get(mm_dd, [])
        years_entries: list[tuple[str, list[dict]]] = []

        if rows:
            # Load entries and sort by year desc, then creationDate desc
            loaded: list[tuple[str, str, Path, dict]] = []
            for year, date_key, json_path in rows:
                if not json_path.exists():
                    continue
                with open(json_path, encoding="utf-8") as f:
                    entry = json.load(f)
                loaded.append((year, date_key, json_path, entry))
            # Sort by year desc, then creationDate desc within year
            loaded.sort(key=lambda x: (x[0], x[3].get("creationDate", "") or ""), reverse=True)

            # Group by year
            current_year: str | None = None
            current_list: list[dict] = []
            for year, date_key, json_path, entry in loaded:
                if year != current_year:
                    if current_list:
                        years_entries.append((current_year, current_list))
                    current_year = year
                    current_list = []
                entry_output_dir = output_dir_for_date_key(entries_dir, date_key)
                # OTD page is at entries/on-this-day/ — one level up to entries/, then YYYY/MM/photos/
                photo_src_prefix = f"../{year}/{json_path.parent.name}/"
                ctx = _entry_context_for_otd(entry, entry_output_dir, photo_src_prefix)
                current_list.append(ctx)
            if current_list and current_year:
                years_entries.append((current_year, current_list))

        index_url = "../../index.html"
        calendar_url = "../../calendar.html"
        media_url = "../../media.html"
        map_url = "../../map.html"

        context = {
            "title": title,
            "day_label": day_label,
            "mm_dd": mm_dd,
            "years_entries": years_entries,
            "prev_url": prev_url,
            "next_url": next_url,
            "prev_label": prev_label,
            "next_label": next_label,
            "index_url": index_url,
            "calendar_url": calendar_url,
            "media_url": media_url,
            "map_url": map_url,
            "css_path": css_path,
        }
        html = template.render(context)
        (otd_dir / f"{mm_dd}.html").write_text(html, encoding="utf-8")
