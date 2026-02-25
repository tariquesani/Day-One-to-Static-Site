"""Helpers for building navigation tab URLs shared across archive pages."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


_TAB_FILES: Dict[str, str] = {
    "index_url": "index.html",
    "calendar_url": "calendar.html",
    "media_url": "media.html",
    "map_url": "map.html",
    "search_url": "search.html",
}


def tab_urls_for_root() -> Dict[str, str]:
    """Return tab URLs for pages that live at the archive root."""
    return dict(_TAB_FILES)


def tab_urls_for_page(archive_root: Path, output_dir: Path) -> Dict[str, str]:
    """
    Return tab URLs relative to a given output_dir.

    archive_root is the directory that contains index.html, calendar.html, etc.
    output_dir is the directory of the page being rendered.
    """
    archive_root = Path(archive_root)
    output_dir = Path(output_dir)
    urls: Dict[str, str] = {}
    for key, filename in _TAB_FILES.items():
        target = archive_root / filename
        rel = os.path.relpath(target, output_dir).replace("\\", "/")
        urls[key] = rel
    return urls

