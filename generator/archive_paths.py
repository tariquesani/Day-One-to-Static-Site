"""Shared date parsing and archive path logic for Day One entries."""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def parse_date(date_str: str) -> str:
    """Extract YYYY-MM-DD from ISO 8601 date string (UTC)."""
    return date_str[:10] if date_str else ""


def _creation_date_local_yyyy_mm_dd(creation_date: str, timezone_name: str | None) -> str:
    """
    Return YYYY-MM-DD for the entry's creation moment in the given timezone.
    If timezone_name is None or invalid, returns the UTC date (parse_date).
    """
    if not creation_date:
        return ""
    if not timezone_name:
        return parse_date(creation_date)
    try:
        dt = datetime.fromisoformat(creation_date.replace("Z", "+00:00"))
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        try:
            tz = ZoneInfo(timezone_name)
        except Exception:
            # Invalid timezone name, fall back to UTC
            return parse_date(creation_date)
        local = dt.astimezone(tz)
        return local.strftime("%Y-%m-%d")
    except Exception:
        # Any error in parsing/conversion, fall back to UTC
        return parse_date(creation_date)


def assign_date_keys(entries_sorted: list[dict]) -> list[tuple[str, dict]]:
    """Build (date_key, entry) for each entry, ordered earliest first."""
    result: list[tuple[str, dict]] = []
    counts: dict[str, int] = defaultdict(int)

    for entry in entries_sorted:
        creation_date = entry.get("creationDate", "")
        tz_name = (entry.get("location") or {}).get("timeZoneName")
        date_part = _creation_date_local_yyyy_mm_dd(creation_date, tz_name)
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


def prev_next_map(manifest_path: Path) -> dict[str, tuple[str | None, str | None]]:
    """Return a mapping of date_key -> (prev_key, next_key) from a manifest."""
    if not manifest_path.exists():
        return {}

    with open(manifest_path, encoding="utf-8") as f:
        data = json.load(f)

    entries = data.get("entries", [])
    # Row format: [uuid, date_key, html_path, creation_date] or legacy [date_key, html_path, creation_date]
    keys: list[str] = [
        row[1] if len(row) >= 4 else row[0]
        for row in entries
        if isinstance(row, list) and row
    ]

    prev_next: dict[str, tuple[str | None, str | None]] = {}
    for i, key in enumerate(keys):
        prev_key = keys[i - 1] if i > 0 else None
        next_key = keys[i + 1] if i + 1 < len(keys) else None
        prev_next[key] = (prev_key, next_key)

    return prev_next
