"""Shared date parsing and archive path logic for Day One entries."""

from collections import defaultdict
from pathlib import Path


def parse_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from ISO 8601 date string."""
    return date_str[:10] if date_str else ""


def assign_date_keys(entries_sorted: list[dict]) -> list[tuple[str, dict]]:
    """Build (date_key, entry) for each entry, ordered earliest first."""
    result: list[tuple[str, dict]] = []
    counts: dict[str, int] = defaultdict(int)

    for entry in entries_sorted:
        creation_date = entry.get("creationDate", "")
        date_part = parse_date(creation_date)
        count = counts[date_part]
        counts[date_part] += 1

        date_key = date_part if count == 0 else f"{date_part}_{count}"
        result.append((date_key, entry))

    return result


def html_path_for_date_key(date_key: str) -> str:
    """Return the relative HTML path for an entry (e.g. 2026/02/2026-02-03.html)."""
    date_part = date_key.split("_")[0]
    parts = date_part.split("-")
    if len(parts) >= 2:
        year, month = parts[0], parts[1]
        return f"{year}/{month}/{date_key}.html"
    return f"{date_key}.html"


def output_dir_for_date_key(archive_entries_dir: Path, date_key: str) -> Path:
    """Return the output directory for an entry (e.g. archive/entries/2026/02/)."""
    date_part = date_key.split("_")[0]
    parts = date_part.split("-")
    year, month = (parts[0], parts[1]) if len(parts) >= 2 else ("0000", "00")
    return archive_entries_dir / year / month
