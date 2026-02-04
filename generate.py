"""Orchestrate generation of the Day One static archive."""

from pathlib import Path

from generator import create_or_update, pick_zip_path, unzip_to_folder, write_entry_jsons
from generator.entry_html import generate_all_entry_html


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
            create_or_update(dayone_json, manifest_path)
            print(f"Manifest updated: {manifest_path}")
            write_entry_jsons(dayone_json, entries_dir)
            print("Entry JSONs written")
            generate_all_entry_html(import_dir, entries_dir, manifest_path)
            print("Entry HTMLs written")


if __name__ == "__main__":
    main()
