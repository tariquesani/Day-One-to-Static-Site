"""Create or update entries/manifest.json from Day One export JSON."""

import json
from pathlib import Path

from generator.archive_paths import assign_date_keys, html_path_for_date_key


def create_or_update(dayone_json_path: str | Path, manifest_path: str | Path) -> None:
    """
    Parse Day One export JSON and either create manifest.json or merge into existing.
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
        (date_key, html_path_for_date_key(date_key), entry.get("creationDate", ""))
        for date_key, entry in rows
    ]

    # Load existing manifest if present
    existing_by_key: dict[str, tuple[str, str]] = {}  # date_key -> (html_path, creation_date)
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        for row in manifest.get("entries", []):
            if len(row) >= 2:
                date_key, html_path = row[0], row[1]
                creation_date = row[2] if len(row) >= 3 else _infer_creation_date(date_key)
                existing_by_key[date_key] = (html_path, creation_date)

    # Merge: new overwrites/adds to existing
    for date_key, html_path, creation_date in new_rows:
        existing_by_key[date_key] = (html_path, creation_date)

    # Sort by creation_date (earliest first)
    sorted_items = sorted(
        existing_by_key.items(),
        key=lambda x: (x[1][1], x[0]),  # creation_date, then date_key for tiebreak
    )
    entries = [[date_key, html_path, creation_date] for date_key, (html_path, creation_date) in sorted_items]

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, indent=2, ensure_ascii=False)


def _infer_creation_date(date_key: str) -> str:
    """Infer a sortable creation_date from date_key when not stored (legacy manifest)."""
    return date_key
