"""Create or update entries/manifest.json from Day One export JSON.

Manifest is keyed by entry UUID so the same entry keeps one row when date_key
changes (e.g. after timezone fix). Row format: [uuid, date_key, html_path, creation_date].
"""

import json
from pathlib import Path

from generator.archive_paths import assign_date_keys, html_path_for_date_key


def create_or_update(dayone_json_path: str | Path, manifest_path: str | Path) -> None:
    """
    Parse Day One export JSON and either create manifest.json or merge into existing.
    Merge is by entry UUID so one row per entry; date_key can change (e.g. timezone fix).
    Entries are ordered by creationDate (earliest first).
    """
    path = Path(dayone_json_path)
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries_raw = data.get("entries", [])
    entries_sorted = sorted(entries_raw, key=lambda e: e.get("creationDate", ""))
    rows = assign_date_keys(entries_sorted)
    new_rows = [
        (
            entry.get("uuid", ""),
            date_key,
            html_path_for_date_key(date_key),
            entry.get("creationDate", ""),
        )
        for date_key, entry in rows
    ]

    # Load existing manifest: key by UUID (or date_key if UUID missing)
    existing_by_uuid: dict[str, tuple[str, str, str]] = {}  # key -> (date_key, html_path, creation_date)
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        for row in manifest.get("entries", []):
            if len(row) >= 4:
                uuid, date_key, html_path, creation_date = row[0], row[1], row[2], row[3]
                key = uuid or date_key
                existing_by_uuid[key] = (date_key, html_path, creation_date)

    # Merge: one row per UUID (or per date_key if UUID missing); date_key can change
    for uuid, date_key, html_path, creation_date in new_rows:
        key = uuid or date_key
        existing_by_uuid[key] = (date_key, html_path, creation_date)

    # Sort by creation_date (earliest first)
    sorted_items = sorted(
        existing_by_uuid.items(),
        key=lambda x: (x[1][2], x[1][0]),  # creation_date, then date_key for tiebreak
    )
    entries = [
        [uuid, date_key, html_path, creation_date]
        for uuid, (date_key, html_path, creation_date) in sorted_items
    ]

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, indent=2, ensure_ascii=False)
