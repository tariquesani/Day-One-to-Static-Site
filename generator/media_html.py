"""Generate archive/media.html and entries/photo-index.json for all photos.

The media grid shows newest photos first (by entry creation order, then
in-entry order). The photo index JSON is ordered in journal order
(oldest first) and is used by the lightbox JS to traverse photos across
entries.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from generator.entry_html import _load_manifest_full
from generator.index_html import _year_range_from_manifest
from generator.nav_context import tab_urls_for_root
from generator.text_to_html import _get_photo_meta_by_identifier, get_photo_filenames_for_entry


def _photo_date_parts(photo_meta: dict | None, entry: dict) -> tuple[str, str, str]:
    """
    Return (iso_date, day_label, month_year) for a photo.

    Prefer the photo's own date; fall back to entry.creationDate.
    """
    iso = ""
    if photo_meta and photo_meta.get("date"):
        iso = photo_meta["date"]
    else:
        iso = entry.get("creationDate", "") or ""

    if not iso:
        return ("", "", "")

    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        day_label = dt.strftime("%d")
        month_year = dt.strftime("%B %Y")
        iso_out = dt.strftime("%Y-%m-%d")
        return (iso_out, day_label, month_year)
    except Exception:
        # Fallbacks if parsing fails
        day_label = iso[8:10] if len(iso) >= 10 else ""
        month_year = ""
        if len(iso) >= 7:
            try:
                year = int(iso[:4])
                month = int(iso[5:7])
                dt2 = datetime(year, month, 1)
                month_year = dt2.strftime("%B %Y")
            except Exception:
                month_year = iso[:7]
        return (iso[:10], day_label, month_year)


def _build_photo_lists(
    manifest_path: Path,
    entries_dir: Path,
) -> tuple[list[dict], list[dict]]:
    """
    Build (photos_chrono, photos_grid) lists.

    photos_chrono: oldest-first list for lightbox traversal.
    photos_grid: newest-first list for media grid display.
    """
    manifest_full = _load_manifest_full(manifest_path)
    if not manifest_full:
        return ([], [])

    entries_dir = Path(entries_dir)
    photos_chrono: list[dict] = []

    for date_key, html_path, _creation_date in manifest_full:
        date_part = date_key.split("_")[0]
        if len(date_part) < 7:
            continue
        parts = date_part.split("-")
        year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
        entry_json_path = entries_dir / year / month / f"{date_key}.json"
        if not entry_json_path.exists():
            continue

        with open(entry_json_path, encoding="utf-8") as f:
            entry = json.load(f)

        photos_dir = entry_json_path.parent / "photos"
        id_and_filenames = get_photo_filenames_for_entry(entry, photos_dir)
        if not id_and_filenames:
            continue

        photos_meta = entry.get("photos", []) or []

        for identifier, filename in id_and_filenames:
            photo_meta = _get_photo_meta_by_identifier(photos_meta, identifier)
            iso_date, day_label, month_year = _photo_date_parts(photo_meta, entry)
            entry_href = f"entries/{html_path}#{identifier}"
            image_url = f"entries/{year}/{month}/photos/{filename}"

            photos_chrono.append(
                {
                    "id": identifier,
                    "entry_href": entry_href,
                    "image_url": image_url,
                    "date_iso": iso_date,
                    "day_label": day_label,
                    "month_year": month_year,
                }
            )

    # Grid wants newest-first; manifest_full is oldest-first by design.
    photos_grid = list(reversed(photos_chrono))
    return (photos_chrono, photos_grid)


def generate_media_html(
    archive_root: Path,
    entries_dir: Path,
    manifest_path: Path,
) -> None:
    """Generate archive/media.html and entries/photo-index.json."""
    manifest_path = Path(manifest_path)
    if not manifest_path.exists():
        return

    entries_dir = Path(entries_dir)
    archive_root = Path(archive_root)

    photos_chrono, photos_grid = _build_photo_lists(manifest_path, entries_dir)
    if not photos_chrono:
        # No photos; skip media.html but still write an empty index for robustness.
        photo_index_path = entries_dir / "photo-index.json"
        photo_index_path.write_text("[]", encoding="utf-8")
        return

    # Write global photo index (journal order, oldest-first) for lightbox traversal.
    photo_index_path = entries_dir / "photo-index.json"
    photo_index_path.write_text(json.dumps(photos_chrono, ensure_ascii=False, indent=2), encoding="utf-8")

    # Render media.html with newest-first grid.
    templates_dir = Path(__file__).resolve().parent / "templates"
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("media.html")

    tab_urls = tab_urls_for_root()
    context = {
        "css_path": "assets/css/",
        "js_path": "assets/js/",
        "active_tab": "media",
        "tab_urls": tab_urls,
        "year_range": _year_range_from_manifest(manifest_path),
        "photos": photos_grid,
        "photo_index_url": "entries/photo-index.json",
    }

    html = template.render(context)
    media_path = archive_root / "media.html"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_text(html, encoding="utf-8")

