"""Regenerate only the On This Day (OTD) pages from existing entry JSONs."""

import sys
import time
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator.otd_html import generate_otd_pages


def main() -> None:
    entries_dir = _project_root / "archive" / "entries"
    if not entries_dir.exists():
        print("archive/entries not found. Run the full generator first.")
        return

    start = time.perf_counter()
    generate_otd_pages(entries_dir)
    elapsed = time.perf_counter() - start

    otd_dir = entries_dir / "on-this-day"
    count = len(list(otd_dir.glob("*.html"))) if otd_dir.exists() else 0
    print(f"Generated {count} OTD pages in {elapsed:.2f}s.")


if __name__ == "__main__":
    main()
