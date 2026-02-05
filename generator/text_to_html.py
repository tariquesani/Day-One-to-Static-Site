"""Convert entry text to HTML, resolving photo references and copying photos."""

import re
import shutil
from pathlib import Path

import markdown


# Match ![](identifier) or ![](dayone-moment://identifier)
PHOTO_REF_RE = re.compile(r"!\[([^\]]*)\]\((?:dayone-moment://)?([^)]+)\)")


def _find_photo_file(import_dir: Path, identifier: str, photos_meta: list[dict]) -> Path | None:
    """Locate the photo file in the Day One export by identifier or md5."""
    # Build lookup from photos metadata
    by_id: dict[str, dict] = {}
    for p in photos_meta:
        if "identifier" in p:
            by_id[p["identifier"]] = p

    meta = by_id.get(identifier) if by_id else None

    # Search locations: Photos/, photos/, root (Day One export structure)
    search_dirs: list[Path] = []
    if import_dir.exists() and import_dir.is_dir():
        for name in ["Photos", "photos", ""]:
            d = import_dir / name if name else import_dir
            if d.exists() and d.is_dir():
                search_dirs.append(d)
        if not search_dirs:
            search_dirs.append(import_dir)

    # Try by md5 first (common in Day One exports)
    if meta and "md5" in meta:
        md5_val = meta["md5"]
        ext = meta.get("type", "jpg").lower()
        if ext == "jpeg":
            ext = "jpg"
        for search_dir in search_dirs:
            for f in search_dir.iterdir():
                if f.is_file() and (f.stem == md5_val or f.name == md5_val or md5_val in f.name):
                    return f

    # Try by identifier
    for search_dir in search_dirs:
        for f in search_dir.iterdir():
            if f.is_file() and identifier in (f.stem, f.name):
                return f

    return None


def entry_text_to_html(
    entry: dict,
    import_dir: Path,
    photos_output_dir: Path,
) -> str:
    """
    Convert entry text to HTML. Resolves photo refs, copies photos to photos_output_dir,
    replaces refs with photos/filename, then converts Markdown to HTML.
    """
    text = entry.get("text", "") or ""
    photos_meta = entry.get("photos", []) or []

    # Build identifier -> dest path map as we process
    refs: dict[str, str] = {}  # identifier -> "photos/filename"

    def replace_ref(m: re.Match) -> str:
        alt, identifier = m.group(1), m.group(2).strip()
        if identifier in refs:
            return f"![{alt}]({refs[identifier]})"

        src = _find_photo_file(import_dir, identifier, photos_meta)
        if not src or not src.exists():
            return ""  # Drop broken refs

        photos_output_dir.mkdir(parents=True, exist_ok=True)
        dest_name = src.name
        dest_path = photos_output_dir / dest_name
        if not dest_path.exists() or src.stat().st_mtime > dest_path.stat().st_mtime:
            shutil.copy2(src, dest_path)

        rel_path = f"photos/{dest_name}"
        refs[identifier] = rel_path
        return f"![{alt}]({rel_path})"

    processed = PHOTO_REF_RE.sub(replace_ref, text)

    html = markdown.markdown(
        processed,
        extensions=["nl2br"],
        output_format="html5",
    )
    return html


def _first_photo_filename_from_photos_dir(
    entry: dict,
    photos_dir: Path,
) -> str | None:
    """
    Resolve the first image in the entry text to a filename that already exists
    in photos_dir (e.g. from when the entry HTML was generated). Uses entry
    metadata (identifier, md5) to match files in photos_dir; does not use
    import_dir, so it works for entries from any import.
    """
    text = entry.get("text", "") or ""
    photos_meta = entry.get("photos", []) or []
    match = PHOTO_REF_RE.search(text)
    if not match:
        return None
    identifier = match.group(2).strip()
    by_id: dict[str, dict] = {}
    for p in photos_meta:
        if "identifier" in p:
            by_id[p["identifier"]] = p
    meta = by_id.get(identifier) if by_id else None
    if not photos_dir.exists():
        return None
    files_in_dir = list(photos_dir.iterdir())
    # Match by md5 (Day One often names export files by md5)
    if meta and "md5" in meta:
        md5_val = meta["md5"]
        for f in files_in_dir:
            if f.is_file() and (f.stem == md5_val or f.name == md5_val or md5_val in f.name):
                return f.name
    # Fallback: match by identifier in filename
    for f in files_in_dir:
        if f.is_file() and identifier in (f.stem, f.name):
            return f.name
    return None


def get_first_photo_filename(
    entry: dict,
    import_dir: Path,
    photos_output_dir: Path,
) -> str | None:
    """
    Return the filename of the first image in the entry, if it already exists in
    photos_output_dir. Prefer resolving from photos already in photos_output_dir
    (works for entries from any import); fall back to import_dir only for
    current-import entries whose photos_dir might not exist yet.
    """
    # Prefer: find filename by matching entry metadata to files already in photos_dir
    name = _first_photo_filename_from_photos_dir(entry, photos_output_dir)
    if name:
        return name
    # Fallback: resolve from import (for current import before entry HTML is regenerated)
    text = entry.get("text", "") or ""
    photos_meta = entry.get("photos", []) or []
    match = PHOTO_REF_RE.search(text)
    if not match:
        return None
    identifier = match.group(2).strip()
    src = _find_photo_file(import_dir, identifier, photos_meta)
    if not src:
        return None
    dest_name = src.name
    dest_path = photos_output_dir / dest_name
    if not dest_path.exists():
        return None
    return dest_name
