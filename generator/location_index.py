"""Generate entries/location-index.json for the map page."""

import json
from pathlib import Path

from generator.archive_paths import html_path_for_date_key


def build_location_index(entries_dir: Path) -> None:
    """
    Scan all entry JSONs under entries_dir, collect entries with location
    (latitude/longitude), and write entries/location-index.json.
    Output: lat, lng, date (YYYY-MM-DD), path (entries/.../...html), place.
    Sorted by creationDate descending. No clustering or aggregation.
    """
    entries_dir = Path(entries_dir)
    out_path = entries_dir / "location-index.json"

    locations: list[dict] = []

    for json_path in entries_dir.rglob("*.json"):
        if json_path.name in ("manifest.json", "location-index.json"):
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

        locations.append({
            "lat": float(loc["latitude"]),
            "lng": float(loc["longitude"]),
            "date": date_ymd,
            "path": path,
            "place": place,
            "_creationDate": entry.get("creationDate", ""),
        })

    locations.sort(key=lambda x: x["_creationDate"], reverse=True)
    for item in locations:
        del item["_creationDate"]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"locations": locations}, f, indent=2, ensure_ascii=False)
