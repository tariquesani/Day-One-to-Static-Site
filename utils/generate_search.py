"""Generate entries/search-index.json for client-side search (e.g. MiniSearch)."""

import json
import re
import sys
import time
from pathlib import Path

# Allow importing generator when run from project root or from utils/
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from generator import entry_helpers
from generator.archive_paths import html_path_for_date_key

# Match ![](identifier) or ![](dayone-moment://identifier)
_PHOTO_REF_RE = re.compile(r"!\[([^\]]*)\]\((?:dayone-moment://)?([^)]+)\)")


def _first_photo_filename_from_photos_dir(entry: dict, photos_dir: Path) -> str | None:
    """Resolve first image in entry text to a filename in photos_dir."""
    text = entry.get("text", "") or ""
    photos_meta = entry.get("photos", []) or []
    match = _PHOTO_REF_RE.search(text)
    if not match:
        return None
    identifier = match.group(2).strip()
    by_id: dict[str, dict] = {p["identifier"]: p for p in photos_meta if "identifier" in p}
    meta = by_id.get(identifier) if by_id else None
    if not photos_dir.exists():
        return None
    files_in_dir = list(photos_dir.iterdir())
    if meta and "md5" in meta:
        md5_val = meta["md5"]
        for f in files_in_dir:
            if f.is_file() and (f.stem == md5_val or f.name == md5_val or md5_val in f.name):
                return f.name
    for f in files_in_dir:
        if f.is_file() and identifier in (f.stem, f.name):
            return f.name
    return None


def _plain_text(entry: dict, max_content_len: int = 50000) -> str:
    """
    Extract plain text from entry for search indexing.
    Strips markdown (images, links, headers), unescapes, and truncates if very long.
    """
    raw = (entry.get("text") or "").strip()
    if not raw:
        return ""

    def unescape(s: str) -> str:
        return re.sub(r"\\([\\`*_{}\[\]()#+\-.!])", r"\1", s)

    raw = unescape(raw)
    # Remove image syntax: ![](url) or ![alt](url)
    raw = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", raw)
    # Remove link syntax but keep text: [text](url) -> text
    raw = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", raw)
    # Strip # header markers (at start of line)
    raw = re.sub(r"^#+\s*", "", raw, flags=re.MULTILINE)
    # Inline markdown: **bold** __bold__ *italic* _italic_ `code`
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)
    raw = re.sub(r"__([^_]+)__", r"\1", raw)
    raw = re.sub(r"\*([^*]+)\*", r"\1", raw)
    raw = re.sub(r"_([^_]+)_", r"\1", raw)
    raw = re.sub(r"`([^`]+)`", r"\1", raw)
    # Collapse runs of whitespace/newlines to a single space
    raw = re.sub(r"\s+", " ", raw).strip()
    if max_content_len and len(raw) > max_content_len:
        raw = raw[:max_content_len] + "…"
    return raw


def _load_manifest(manifest_path: Path) -> list[tuple[str, str, str]]:
    """Return list of (date_key, html_path, creation_date)."""
    if not manifest_path.exists():
        return []
    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("entries", [])
    result: list[tuple[str, str, str]] = []
    for row in entries:
        if len(row) >= 4:
            result.append((row[1], row[2], row[3]))
        elif len(row) >= 3:
            result.append((row[0], row[1], row[2]))
        elif len(row) >= 2:
            result.append((row[0], row[1], row[0]))
    return result


def build_search_index(entries_dir: Path, out_path: Path, *, verbose: bool = True) -> int:
    """
    Read manifest and all entry JSONs, build a list of search documents,
    and write search-index.json. Returns the number of documents indexed.
    """
    entries_dir = Path(entries_dir)
    manifest_path = entries_dir / "manifest.json"
    manifest = _load_manifest(manifest_path)
    if not manifest:
        if verbose:
            print("No entries in manifest.")
        return 0

    total = len(manifest)
    if verbose:
        print(f"Processing {total} entries from manifest ...")

    documents: list[dict] = []
    skipped = 0
    progress_interval = max(1, total // 20)  # ~20 progress lines, or every 1 if small
    start = time.perf_counter()

    for i, (date_key, html_path, creation_date) in enumerate(manifest, start=1):
        date_part = date_key.split("_")[0]
        parts = date_part.split("-")
        year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
        entry_json_path = entries_dir / year / month / f"{date_key}.json"
        if not entry_json_path.exists():
            skipped += 1
            continue
        try:
            with open(entry_json_path, encoding="utf-8") as f:
                entry = json.load(f)
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue

        tags = list(entry.get("tags") or [])
        content = _plain_text(entry)
        excerpt = entry_helpers.index_snippet(entry, max_len=200)
        location = entry_helpers.get_location(entry)

        # URL from site root: entries/YYYY/MM/date_key.html
        url = "entries/" + html_path.replace("\\", "/")

        photos_dir = entry_json_path.parent / "photos"
        first_photo = _first_photo_filename_from_photos_dir(entry, photos_dir)
        thumbnail_url: str | None = None
        if first_photo:
            path_parts = url.replace("\\", "/").split("/")
            thumbnail_url = "/".join(path_parts[:-1]) + "/photos/" + first_photo

        documents.append({
            "id": date_key,
            "url": url,
            "date": creation_date[:10] if creation_date else date_part,
            "creation_date": creation_date or "",
            "location": location,
            "tags": tags,
            "content": content,
            "excerpt": excerpt,
            "thumbnail_url": thumbnail_url,
        })

        if verbose and (i % progress_interval == 0 or i == total):
            print(f"  {i:,} / {total:,} indexed ...", flush=True)

    if verbose:
        elapsed = time.perf_counter() - start
        print(f"Writing {len(documents):,} documents to {out_path.name} ...", flush=True)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"documents": documents}, f, indent=2, ensure_ascii=False)

    if verbose:
        if skipped:
            print(f"Skipped {skipped:,} (missing or invalid JSON).")
        print(f"Done in {time.perf_counter() - start:.2f}s.")

    return len(documents)


def main() -> None:
    entries_dir = _project_root / "archive" / "entries"
    out_path = entries_dir / "search-index.json"

    if not entries_dir.exists():
        print(f"Entries directory not found: {entries_dir}. Run a full generation first.")
        sys.exit(1)

    manifest_path = entries_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}. Run a full generation first.")
        sys.exit(1)

    print(f"Output: {out_path.relative_to(_project_root)}")
    count = build_search_index(entries_dir, out_path, verbose=True)
    print(f"Wrote {count:,} document(s).")


if __name__ == "__main__":
    main()
