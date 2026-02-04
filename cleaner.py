"""Remove imported, extracted, and generated files to restore a clean slate."""

import shutil
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent
    imports_dir = project_root / "_imports"
    entries_dir = project_root / "archive" / "entries"

    to_remove: list[str] = []
    if imports_dir.exists():
        to_remove.append(str(imports_dir))
    if entries_dir.exists():
        to_remove.append(f"{entries_dir}/ (manifest, YYYY/MM/*.json, photos, etc.)")

    if not to_remove:
        print("Nothing to clean — _imports and archive/entries are already empty or missing.")
        return

    print("This will delete:")
    for path in to_remove:
        print(f"  - {path}")
    print()
    response = input("Continue? [y/N] ").strip().lower()

    if response != "y":
        print("Aborted.")
        return

    if imports_dir.exists():
        shutil.rmtree(imports_dir)
        print(f"Removed {imports_dir}")

    if entries_dir.exists():
        for item in entries_dir.iterdir():
            if item.is_file():
                item.unlink()
                print(f"Removed {item}")
            else:
                shutil.rmtree(item)
                print(f"Removed {item}/")

    print("Done. Clean slate restored.")


if __name__ == "__main__":
    main()
