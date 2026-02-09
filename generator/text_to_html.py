"""Convert entry text to HTML, resolving photo references and copying photos."""

import html
import re
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import markdown


# Match ![](identifier) or ![](dayone-moment://identifier)
PHOTO_REF_RE = re.compile(r"!\[([^\]]*)\]\((?:dayone-moment://)?([^)]+)\)")


def _get_photo_meta_by_identifier(photos_meta: list[dict], identifier: str) -> dict | None:
    """Return the photo metadata dict matching the given identifier, if any."""
    for p in photos_meta:
        if p.get("identifier") == identifier:
            return p
    return None


def _get_timezone_name_for_photo(photo_meta: dict | None, entry: dict) -> str:
    """
    Resolve timezone name for a photo.

    Priority:
    1) photo.location.timeZoneName
    2) entry.location.timeZoneName
    3) entry.timeZone
    4) "Asia/Kolkata" (sensible default)
    """
    # 1) timeZoneName on photo location
    if photo_meta:
        loc = photo_meta.get("location") or {}
        tz = loc.get("timeZoneName")
        if tz:
            return tz

    # 2) timeZoneName on entry location
    entry_loc = entry.get("location") or {}
    tz = entry_loc.get("timeZoneName")
    if tz:
        return tz

    # 3) entry-level timeZone (Day One often stores it there)
    tz = entry.get("timeZone")
    if tz:
        return tz

    # 4) Fallback
    return "Asia/Kolkata"


def _format_photo_datetime(photo_meta: dict | None, entry: dict) -> str:
    """
    Format the photo's date/time in its appropriate timezone.

    Example output: "03 Jan 2024, 07:28 AM"
    """
    if not photo_meta:
        return ""

    iso_date = photo_meta.get("date")
    if not iso_date:
        return ""

    tz_name = _get_timezone_name_for_photo(photo_meta, entry)

    try:
        # Day One dates are typically UTC with trailing "Z"
        dt_utc = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        dt_local = dt_utc.astimezone(ZoneInfo(tz_name))
        return dt_local.strftime("%d %b %Y, %I:%M %p")
    except Exception:
        # Fallback: show the raw date without timezone conversion
        try:
            dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
            return dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            return iso_date


def _format_photo_location(photo_meta: dict | None, entry: dict) -> str:
    """
    Format location as 'placeName, localityName, country'.

    Prefer the photo's own location; fall back to entry location.
    """
    loc = {}
    if photo_meta and photo_meta.get("location"):
        loc = photo_meta["location"]
    elif entry.get("location"):
        loc = entry["location"]

    place = (loc.get("placeName") or "").strip() if loc else ""
    locality = (loc.get("localityName") or "").strip() if loc else ""
    country = (loc.get("country") or "").strip() if loc else ""

    parts = [p for p in (place, locality, country) if p]
    return ", ".join(parts)


def _build_photo_caption(photo_meta: dict | None, entry: dict) -> str:
    """Combine formatted datetime and location into a single caption string."""
    dt_text = _format_photo_datetime(photo_meta, entry)
    loc_text = _format_photo_location(photo_meta, entry)

    parts = [p for p in (dt_text, loc_text) if p]
    return " · ".join(parts)


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

    # Build identifier -> rendered HTML map as we process
    refs: dict[str, str] = {}  # identifier -> full <figure> HTML

    def replace_ref(m: re.Match) -> str:
        alt, identifier = m.group(1), m.group(2).strip()
        if identifier in refs:
            return refs[identifier]

        src = _find_photo_file(import_dir, identifier, photos_meta)
        if not src or not src.exists():
            return ""  # Drop broken refs

        photos_output_dir.mkdir(parents=True, exist_ok=True)
        dest_name = src.name
        dest_path = photos_output_dir / dest_name
        if not dest_path.exists() or src.stat().st_mtime > dest_path.stat().st_mtime:
            shutil.copy2(src, dest_path)

        rel_path = f"photos/{dest_name}"

        # Build caption using photo metadata and entry-level fallbacks
        photo_meta = _get_photo_meta_by_identifier(photos_meta, identifier)
        caption = _build_photo_caption(photo_meta, entry)

        alt_escaped = html.escape(alt or "")
        caption_html = (
            f"<figcaption>{html.escape(caption)}</figcaption>" if caption else ""
        )

        figure_html = (
            f'<figure class="entry-photo">'
            f'<img src="{rel_path}" alt="{alt_escaped}">{caption_html}'
            f"</figure>"
        )

        refs[identifier] = figure_html
        return figure_html

    processed = PHOTO_REF_RE.sub(replace_ref, text)

    rendered_html = markdown.markdown(
        processed,
        extensions=["nl2br"],
        output_format="html5",
    )
    return rendered_html


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
