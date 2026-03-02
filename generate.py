"""Orchestrate generation of the Day One static archive."""

import json
import sys
from pathlib import Path

from generator import create_or_update, pick_zip_path, unzip_to_folder, write_entry_jsons
from generator.archive_paths import assign_date_keys, output_dir_for_date_key, prev_next_map
from generator.calendar_html import generate_calendar_html
from generator.entry_html import generate_entry_html
from generator.index_html import generate_index_html
from generator.location_index import build_location_index
from generator.media_html import generate_media_html
from generator.otd_html import generate_otd_pages
from utils.generate_search import build_search_index


def _normalize_import_json_place_names(dayone_json: Path) -> None:
    """
    Normalize known place name spellings directly in the imported Day One JSON.

    Currently:
    - If location.placeName is exactly "Sanis", change it to "SANI's".
    """
    if not dayone_json.exists():
        return

    with open(dayone_json, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    changed = False

    for entry in entries:
        # Normalize entry-level location
        loc = entry.get("location")
        if isinstance(loc, dict):
            place_name = (loc.get("placeName") or "").strip()
            if place_name == "Sanis":
                loc["placeName"] = "SANI's"
                changed = True

        # Normalize per-photo locations (captions use photo.location first)
        photos = entry.get("photos") or []
        for photo in photos:
            photo_loc = photo.get("location")
            if not isinstance(photo_loc, dict):
                continue
            p_name = (photo_loc.get("placeName") or "").strip()
            if p_name == "Sanis":
                photo_loc["placeName"] = "SANI's"
                changed = True

    if not changed:
        return

    with open(dayone_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


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
            # Normalize any known place name spelling quirks directly in the import JSON
            # so all downstream processing (manifest, per-entry JSON, HTML) sees the
            # corrected value.
            print("Normalizing place names in imported Day One JSON...")
            _normalize_import_json_place_names(dayone_json)
            print("Place name normalization complete.")
            entries_dir = project_root / "archive" / "entries"
            manifest_path = entries_dir / "manifest.json"

            # Capture neighbor relationships before updating the manifest.
            old_prev_next = prev_next_map(manifest_path)

            print("Updating manifest and per-entry JSON files...")
            create_or_update(dayone_json, manifest_path)
            write_entry_jsons(dayone_json, entries_dir)
            print("Manifest and entry JSON update complete.")

            # Step 1: generate HTML only for entries in the imported Day One JSON.
            with open(dayone_json, encoding="utf-8") as f:
                data = json.load(f)
            entries_raw = data.get("entries", [])
            entries_sorted = sorted(entries_raw, key=lambda e: e.get("creationDate", ""))
            imported_date_keys = [date_key for date_key, _ in assign_date_keys(entries_sorted)]

            # Determine which entries' neighbor relationships changed.
            new_prev_next = prev_next_map(manifest_path)
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
            regen_keys_sorted = sorted(regen_keys)
            total_entries = len(regen_keys_sorted)
            bar_width = 40

            print("Regenerating entry HTML pages...")
            for idx, date_key in enumerate(regen_keys_sorted, start=1):
                entry_json_dir = output_dir_for_date_key(entries_dir, date_key)
                entry_json_path = entry_json_dir / f"{date_key}.json"
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

                # Simple terminal progress bar for entry HTML generation (similar to utils/generate_again.py)
                if total_entries:
                    progress = idx / total_entries
                    filled = int(bar_width * progress)
                    bar = "#" * filled + "-" * (bar_width - filled)
                    sys.stdout.write(f"\rEntries: [{bar}] {idx}/{total_entries}")
                    sys.stdout.flush()

            if total_entries:
                sys.stdout.write("\n")
                print("Entry HTML generation complete.")

            # Keep index.html fresh without regenerating all entry pages.
            archive_root = entries_dir.parent
            print("Generating index.html...")
            generate_index_html(import_dir, archive_root, entries_dir, manifest_path)

            # Calendar: archive/calendar.html (journal-by-date calendar view)
            print("Generating calendar.html...")
            generate_calendar_html(import_dir, archive_root, entries_dir, manifest_path)

            # Media: archive/media.html and entries/photo-index.json (global photo index)
            print("Generating media.html and global photo index...")
            generate_media_html(
                archive_root=archive_root,
                entries_dir=entries_dir,
                manifest_path=manifest_path,
            )

            # On This Day: one page per calendar day (366 pages) under entries/on-this-day/
            print("Generating On This Day pages...")
            generate_otd_pages(entries_dir)

            # Map: location index for map.html (entries with lat/lng only)
            print("Building location index for map...")
            build_location_index(entries_dir)

            # Search index: entries/search-index.json for client-side search
            search_index_path = entries_dir / "search-index.json"
            print("Building search index (this may take a moment)...")
            build_search_index(entries_dir, search_index_path, verbose=True)


if __name__ == "__main__":
    main()
