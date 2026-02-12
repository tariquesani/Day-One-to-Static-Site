"""Regenerate only the map data (entries/location-index.json) from existing entry JSONs."""

import json
import sys
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator.location_index import build_location_index


def main() -> None:
    entries_dir = _project_root / "archive" / "entries"

    if not entries_dir.exists():
        print(f"Entries directory not found: {entries_dir}. Run a full generation first.")
        sys.exit(1)

    build_location_index(entries_dir)

    index_path = entries_dir / "location-index.json"
    if index_path.exists():
        with open(index_path, encoding="utf-8") as f:
            data = json.load(f)
        count = len(data.get("locations", []))
        print(f"Regenerated {index_path.relative_to(_project_root)} with {count} location(s).")
    else:
        print(f"Regenerated {index_path.relative_to(_project_root)}.")


if __name__ == "__main__":
    main()
