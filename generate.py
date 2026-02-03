"""Orchestrate generation of the Day One static archive."""

from pathlib import Path

from generator.manifest import create_or_update
from generator.zip_handler import pick_zip_path, unzip_to_folder


def main():
    path = pick_zip_path()
    if path:
        project_root = Path(__file__).resolve().parent
        temp_dir = project_root / "temp"
        unzip_to_folder(path, temp_dir)
        print(f"Extracted to {temp_dir}")

        dayone_jsons = list(temp_dir.glob("*.json"))
        if dayone_jsons:
            manifest_path = project_root / "archive" / "entries" / "manifest.json"
            create_or_update(dayone_jsons[0], manifest_path)
            print(f"Manifest updated: {manifest_path}")


if __name__ == "__main__":
    main()
