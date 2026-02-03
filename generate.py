"""Orchestrate generation of the Day One static archive."""

from pathlib import Path

from generator.zip_handler import pick_zip_path, unzip_to_folder


def main():
    path = pick_zip_path()
    if path:
        project_root = Path(__file__).resolve().parent
        unzip_to_folder(path, project_root / "temp")
        print(f"Extracted to {project_root / 'temp'}")


if __name__ == "__main__":
    main()
