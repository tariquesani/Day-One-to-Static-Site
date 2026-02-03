"""Create or update entries/manifest.json from Day One export JSON."""

import json
from collections import defaultdict
from pathlib import Path


def _parse_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from ISO 8601 date string."""
    return date_str[:10] if date_str else ""


def _assign_date_keys(entries_sorted: list[dict]) -> list[tuple[str, str, str]]:
    """Build (date_key, html_path, creation_date) for each entry, ordered earliest first."""
    result = []
    # Group by date to assign _1, _2 suffixes for same-day entries
    counts: dict[str, int] = defaultdict(int)

    for entry in entries_sorted:
        creation_date = entry.get("creationDate", "")
        date_part = _parse_date(creation_date)
        count = counts[date_part]
        counts[date_part] += 1

        if count == 0:
            date_key = date_part
        else:
            date_key = f"{date_part}_{count}"

        year, month, _ = date_part.split("-") if len(date_part) == 10 else ("", "", "")
        html_path = f"{year}/{month}/{date_key}.html" if year and month else f"{date_key}.html"

        result.append((date_key, html_path, creation_date))

    return result


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
    new_rows = _assign_date_keys(entries_sorted)

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
