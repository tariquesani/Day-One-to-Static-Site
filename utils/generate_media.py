"""Regenerate only archive/media.html (and entries/photo-index.json) using existing manifest and entry JSONs."""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator.media_html import generate_media_html  # type: ignore  # noqa: E402


def main() -> None:
    entries_dir = _project_root / "archive" / "entries"
    manifest_path = entries_dir / "manifest.json"

    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}. Run a full generation first.")
        return

    archive_root = entries_dir.parent

    print("Regenerating archive/media.html ...")
    start = time.perf_counter()
    generate_media_html(
        archive_root=archive_root,
        entries_dir=entries_dir,
        manifest_path=manifest_path,
    )
    end = time.perf_counter()
    print(f"Done. Wrote {archive_root / 'media.html'} in {end - start:.2f}s.")


if __name__ == "__main__":
    main()

