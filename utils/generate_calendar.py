"""Regenerate only archive/calendar.html using existing manifest and entry JSONs."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator.calendar_html import generate_calendar_html  # type: ignore  # noqa: E402


def _pick_import_dir(imports_base: Path) -> Path | None:
    """
    Return the first subdirectory under imports_base that contains
    a Day One JSON export, or None if none are found.
    """
    if not imports_base.exists():
        return None

    for subdir in sorted(imports_base.iterdir()):
        if not subdir.is_dir():
            continue
        jsons = list(subdir.glob("*.json"))
        if jsons:
            return subdir
    return None


def main() -> None:
    entries_dir = _project_root / "archive" / "entries"
    manifest_path = entries_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}. Run a full generation first.")
        return

    archive_root = entries_dir.parent
    imports_base = _project_root / "_imports"

    # Prefer an import directory (for thumbnail fallback), but gracefully
    # fall back to the archive root if none are present.
    import_dir = _pick_import_dir(imports_base) or archive_root

    print("Regenerating archive/calendar.html ...")
    start = time.perf_counter()
    generate_calendar_html(import_dir, archive_root, entries_dir, manifest_path)
    end = time.perf_counter()
    print(f"Done. Wrote {archive_root / 'calendar.html'} in {end - start:.2f}s.")


if __name__ == "__main__":
    main()
