"""Orchestrate generation of the Day One static archive."""

import json
from pathlib import Path

from generator import create_or_update, pick_zip_path, unzip_to_folder, write_entry_jsons
from generator.archive_paths import assign_date_keys
from generator.entry_html import generate_entry_html, generate_index_html


def _prev_next_map(manifest_path: Path) -> dict[str, tuple[str | None, str | None]]:
    """Return a mapping of date_key -> (prev_key, next_key) from a manifest."""
    if not manifest_path.exists():
        return {}

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    # Row format: [uuid, date_key, html_path, creation_date] or legacy [date_key, html_path, creation_date]
    keys: list[str] = [
        row[1] if len(row) >= 4 else row[0]
        for row in entries
        if isinstance(row, list) and row
    ]

    prev_next: dict[str, tuple[str | None, str | None]] = {}
    for i, key in enumerate(keys):
        prev_key = keys[i - 1] if i > 0 else None
        next_key = keys[i + 1] if i + 1 < len(keys) else None
        prev_next[key] = (prev_key, next_key)

    return prev_next


def main():
    path = pick_zip_path()
    if path:
        project_root = Path(__file__).resolve().parent
        zip_stem = Path(path).stem
        import_dir = project_root / "_imports" / zip_stem
        unzip_to_folder(path, import_dir)
        print(f"Extracted to {import_dir}")

        dayone_jsons = list(import_dir.glob("*.json"))
        if dayone_jsons:
            dayone_json = dayone_jsons[0]
            entries_dir = project_root / "archive" / "entries"
            manifest_path = entries_dir / "manifest.json"

            # Capture neighbor relationships before updating the manifest.
            old_prev_next = _prev_next_map(manifest_path)

            create_or_update(dayone_json, manifest_path)
            write_entry_jsons(dayone_json, entries_dir)

            # Step 1: generate HTML only for entries in the imported Day One JSON.
            with open(dayone_json, encoding="utf-8") as f:
                data = json.load(f)
            entries_raw = data.get("entries", [])
            entries_sorted = sorted(entries_raw, key=lambda e: e.get("creationDate", ""))
            imported_date_keys = [date_key for date_key, _ in assign_date_keys(entries_sorted)]

            # Determine which entries' neighbor relationships changed.
            new_prev_next = _prev_next_map(manifest_path)
            regen_keys: set[str] = set(imported_date_keys)

            for date_key, (new_prev, new_next) in new_prev_next.items():
                old_prev, old_next = old_prev_next.get(date_key, (None, None))
                if old_prev != new_prev or old_next != new_next:
                    regen_keys.add(date_key)

            # Separate imported entries from existing neighbors being rewritten.
            imported_set = set(imported_date_keys)
            neighbor_rewrites = sorted(k for k in regen_keys if k not in imported_set)

            print(f"Imported entries: {len(imported_set)}")
            print(f"Neighbor entries rewritten: {len(neighbor_rewrites)}")

            # Regenerate HTML for imported entries and any entries whose neighbors changed.
            for date_key in sorted(regen_keys):
                date_part = date_key.split("_")[0]
                parts = date_part.split("-")
                year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
                entry_json_path = entries_dir / year / month / f"{date_key}.json"
                if not entry_json_path.exists():
                    continue
                # For entries from this import, use the current unzip folder as the photo source.
                # For existing neighbors being regenerated, derive the photo source from the
                # parent of the JSON file (which already has a photos/ folder).
                photo_source_root = import_dir if date_key in imported_date_keys else entry_json_path.parent
                generate_entry_html(
                    entry_json_path=entry_json_path,
                    date_key=date_key,
                    import_dir=photo_source_root,
                    entries_dir=entries_dir,
                    manifest_path=manifest_path,
                )

            # Keep index.html fresh without regenerating all entry pages.
            archive_root = entries_dir.parent
            generate_index_html(import_dir, archive_root, entries_dir, manifest_path)


if __name__ == "__main__":
    main()
