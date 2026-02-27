"""Regenerate the full static archive from existing _imports folder (no zip picker)."""

import json
import sys
import time
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator import create_or_update, write_entry_jsons
from generator.archive_paths import assign_date_keys, output_dir_for_date_key, prev_next_map
from generator.calendar_html import generate_calendar_html
from generator.media_html import generate_media_html
from generator.entry_html import generate_entry_html
from generator.index_html import generate_index_html
from generator.location_index import build_location_index
from generator.otd_html import generate_otd_pages
from utils.generate_search import build_search_index


def _discover_imports(imports_base: Path) -> list[tuple[Path, Path]]:
    """Return list of (import_dir, dayone_json_path) for each subfolder that has a JSON."""
    if not imports_base.exists():
        return []
    result: list[tuple[Path, Path]] = []
    for subdir in sorted(imports_base.iterdir()):
        if not subdir.is_dir():
            continue
        jsons = list(subdir.glob("*.json"))
        if jsons:
            result.append((subdir, jsons[0]))
    return result


def _date_key_to_import_dir(
    imports_base: Path,
) -> tuple[list[tuple[Path, Path]], dict[str, Path]]:
    """
    Discover all import (subdir, json) pairs and build date_key -> import_dir.
    Later exports overwrite if same date_key appears in multiple.
    """
    pairs = _discover_imports(imports_base)
    date_key_to_dir: dict[str, Path] = {}
    for import_dir, json_path in pairs:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        entries_raw = data.get("entries", [])
        entries_sorted = sorted(entries_raw, key=lambda e: e.get("creationDate", ""))
        for date_key, _ in assign_date_keys(entries_sorted):
            date_key_to_dir[date_key] = import_dir
    return pairs, date_key_to_dir


def main() -> None:
    total_start = time.perf_counter()

    imports_base = _project_root / "_imports"
    entries_dir = _project_root / "archive" / "entries"
    manifest_path = entries_dir / "manifest.json"

    pairs, date_key_to_import_dir = _date_key_to_import_dir(imports_base)
    if not pairs:
        print("No Day One JSONs found under _imports. Add export folders there first.")
        return

    print(f"Found {len(pairs)} import(s) under _imports.")

    # Rebuild manifest and entry JSONs from all imports (order: sorted by subdir name)
    for import_dir, json_path in pairs:
        create_or_update(json_path, manifest_path)
        write_entry_jsons(json_path, entries_dir)
        print(f"  Merged: {import_dir.name}")

    # Regenerate HTML for every entry in the manifest
    prev_next = prev_next_map(manifest_path)
    manifest_entries = list(prev_next.keys())

    entries_html_start = time.perf_counter()
    total_entries = len(manifest_entries)
    bar_width = 40

    for idx, date_key in enumerate(manifest_entries, start=1):
        entry_json_dir = output_dir_for_date_key(entries_dir, date_key)
        entry_json_path = entry_json_dir / f"{date_key}.json"
        if not entry_json_path.exists():
            continue
        # Use the import dir this entry came from; fallback to archive photos dir if unknown
        photo_source = date_key_to_import_dir.get(date_key, entry_json_path.parent)
        generate_entry_html(
            entry_json_path=entry_json_path,
            date_key=date_key,
            import_dir=photo_source,
            entries_dir=entries_dir,
            manifest_path=manifest_path,
        )

        # Simple terminal progress bar for entry HTML generation
        if total_entries:
            progress = idx / total_entries
            filled = int(bar_width * progress)
            bar = "#" * filled + "-" * (bar_width - filled)
            sys.stdout.write(f"\rEntries: [{bar}] {idx}/{total_entries}")
            sys.stdout.flush()

    if total_entries:
        sys.stdout.write("\n")

    # Regenerate index (use first import dir for thumbnail fallback; photos usually in archive)
    archive_root = entries_dir.parent
    first_import_dir = pairs[0][0]

    index_html_start = time.perf_counter()
    generate_index_html(first_import_dir, archive_root, entries_dir, manifest_path)
    index_html_end = time.perf_counter()

    generate_calendar_html(first_import_dir, archive_root, entries_dir, manifest_path)

    generate_media_html(
        archive_root=archive_root,
        entries_dir=entries_dir,
        manifest_path=manifest_path,
    )

    otd_start = time.perf_counter()
    generate_otd_pages(entries_dir)
    otd_end = time.perf_counter()

    build_location_index(entries_dir)

    search_index_path = entries_dir / "search-index.json"
    build_search_index(entries_dir, search_index_path, verbose=True)

    total_end = time.perf_counter()

    # Simple stats
    prev_links = sum(1 for prev, _ in prev_next.values() if prev is not None)
    next_links = sum(1 for _, nxt in prev_next.values() if nxt is not None)
    neighbour_links = prev_links + next_links

    print(f"Regenerated {len(manifest_entries)} entries and index.")
    print("Stats:")
    print(f"  Total imports: {len(pairs)}")
    print(f"  Total entries: {len(manifest_entries)}")
    print(f"  Neighbour links (prev+next): {neighbour_links}")
    print(f"  Time for entry HTML: {index_html_start - entries_html_start:.2f}s")
    print(f"  Time for index.html: {index_html_end - index_html_start:.2f}s")
    print(f"  Time for OTD: {otd_end - otd_start:.2f}s")
    print(f"  Total time: {total_end - total_start:.2f}s")


if __name__ == "__main__":
    main()
