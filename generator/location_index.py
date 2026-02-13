"""Generate entries/location-index.json for the map page."""

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from generator.archive_paths import html_path_for_date_key
from generator import entry_helpers

# Match ![](identifier) or ![](dayone-moment://identifier)
_PHOTO_REF_RE = re.compile(r"!\[([^\]]*)\]\((?:dayone-moment://)?([^)]+)\)")


def _first_photo_filename_from_photos_dir(entry: dict, photos_dir: Path) -> str | None:
    """Resolve first image in entry text to a filename in photos_dir."""
    text = entry.get("text", "") or ""
    photos_meta = entry.get("photos", []) or []
    match = _PHOTO_REF_RE.search(text)
    if not match:
        return None
    identifier = match.group(2).strip()
    by_id: dict[str, dict] = {p["identifier"]: p for p in photos_meta if "identifier" in p}
    meta = by_id.get(identifier) if by_id else None
    if not photos_dir.exists():
        return None
    files_in_dir = list(photos_dir.iterdir())
    if meta and "md5" in meta:
        md5_val = meta["md5"]
        for f in files_in_dir:
            if f.is_file() and (f.stem == md5_val or f.name == md5_val or md5_val in f.name):
                return f.name
    for f in files_in_dir:
        if f.is_file() and identifier in (f.stem, f.name):
            return f.name
    return None


def _date_dow_day(entry: dict) -> tuple[str, str]:
    """Return (dow, day) for entry creationDate, e.g. ('Thu', '12')."""
    creation = entry.get("creationDate", "")
    if not creation:
        return ("", "")
    tz_name = ((entry.get("location") or {}).get("timeZoneName") or entry.get("timeZone")) or "UTC"
    try:
        dt = datetime.fromisoformat(creation.replace("Z", "+00:00"))
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        if tz_name:
            dt = dt.astimezone(ZoneInfo(tz_name))
        return (dt.strftime("%a"), dt.strftime("%d"))
    except Exception:
        return ("", creation[:10].split("-")[-1] if creation else "")


def build_location_index(entries_dir: Path) -> None:
    """
    Scan all entry JSONs under entries_dir, collect entries with location
    (latitude/longitude), and write entries/location-index.json.
    Output: lat, lng, date, path, place, snippet, meta_line, thumbnail_url?, dow, day.
    Sorted by creationDate descending. No clustering or aggregation.
    """
    entries_dir = Path(entries_dir)
    out_path = entries_dir / "location-index.json"

    locations: list[dict] = []

    for json_path in entries_dir.rglob("*.json"):
        if json_path.name in ("manifest.json", "location-index.json", "photo-index.json"):
            continue
        date_key = json_path.stem

        try:
            with open(json_path, encoding="utf-8") as f:
                entry = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue

        loc = entry.get("location")
        if not isinstance(loc, dict) or "latitude" not in loc or "longitude" not in loc:
            continue

        date_ymd = date_key.split("_")[0]
        path = "entries/" + html_path_for_date_key(date_key)
        place = (loc.get("localityName") or loc.get("placeName") or "").strip()
        dow, day = _date_dow_day(entry)
        snippet = entry_helpers.index_snippet(entry)
        meta_line = entry_helpers.index_meta_line(entry)

        photos_dir = json_path.parent / "photos"
        first_photo = _first_photo_filename_from_photos_dir(entry, photos_dir)
        thumbnail_url = None
        if first_photo:
            # path is like entries/2026/02/2026-02-12.html; we need entries/2026/02/photos/filename
            path_parts = path.replace("\\", "/").split("/")
            if len(path_parts) >= 3:
                base = "/".join(path_parts[:-1])
                thumbnail_url = f"{base}/photos/{first_photo}"

        locations.append({
            "lat": float(loc["latitude"]),
            "lng": float(loc["longitude"]),
            "date": date_ymd,
            "path": path,
            "place": place,
            "snippet": snippet,
            "meta_line": meta_line,
            "thumbnail_url": thumbnail_url,
            "dow": dow,
            "day": day,
            "_creationDate": entry.get("creationDate", ""),
        })

    locations.sort(key=lambda x: x["_creationDate"], reverse=True)
    for item in locations:
        del item["_creationDate"]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"locations": locations}, f, indent=2, ensure_ascii=False)
