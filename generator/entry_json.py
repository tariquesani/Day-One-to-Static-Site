"""Write canonical per-entry JSON files from Day One export."""

import json
from pathlib import Path

from generator.archive_paths import assign_date_keys, output_dir_for_date_key


def write_entry_jsons(dayone_json_path: str | Path, archive_entries_dir: str | Path) -> None:
    """
    Copy each entry from the Day One export JSON to its canonical path.
    No modifications — exact copy per entry.
    """
    path = Path(dayone_json_path)
    archive_entries_dir = Path(archive_entries_dir)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    entries_raw = data.get("entries", [])
    entries_sorted = sorted(entries_raw, key=lambda e: e.get("creationDate", ""))
    rows = assign_date_keys(entries_sorted)

    for date_key, entry in rows:
        out_dir = output_dir_for_date_key(archive_entries_dir, date_key)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{date_key}.json"

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
