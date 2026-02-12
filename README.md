# Day One to Static Site

Turn a [Day One](https://dayoneapp.com/) journal export (ZIP) into a self-contained static website. Entries become HTML pages with prev/next navigation, and the archive includes a list view, calendar, media grid, map, and “On This Day” pages. 

I created this project because I have 14 years worth of journal entries and I want them to survive after me and be accessible even without the Day One app. 

## Features

- **Import from ZIP** — Pick a Day One export ZIP; entries are extracted, merged into a manifest, and rendered as HTML.
- **Entry pages** — One HTML file per entry under `archive/entries/YYYY/MM/`, with Markdown → HTML, photos, location, and weather.
- **List view** — `index.html` shows all entries grouped by month with previews and links.
- **Calendar** — `calendar.html` shows a full calendar grid with entry links and optional thumbnails.
- **Media** — `media.html` displays all photos in a grid; `entries/photo-index.json` powers lightbox-style navigation across entries.
- **Map** — `map.html` uses Leaflet and `entries/location-index.json` to show entry locations (lat/lng).
- **On This Day** — One page per calendar day (e.g. `entries/on-this-day/02-12.html`) listing entries from that day across years.
- **Incremental updates** — Re-importing only regenerates changed entries and neighbors; existing data is preserved.

## Requirements

- **Python 3.10+** (uses `zoneinfo` and type hints)
- **Day One export** — From the Day One app: export your journal as a ZIP (JSON + photos).

### Python dependencies

```text
jinja2>=3.0
markdown>=3.0
tzdata>=2024.1
```

Install with:

```bash
pip install -r requirements.txt
```

## Quick start

1. **Export from Day One**  
   In Day One, export your journal as a ZIP (Settings → Export → ZIP). You’ll get a folder with a `.json` file and a `photos` (or similar) directory.

2. **Generate the archive**  
   From the project root:

   ```bash
   python generate.py
   ```

   A file dialog opens — select your Day One export ZIP. The script will:

   - Extract it to `_imports/<zip_stem>/`
   - Create or update `archive/entries/manifest.json` (by entry UUID)
   - Write per-entry JSON under `archive/entries/YYYY/MM/<date_key>.json`
   - Generate entry HTML, `archive/index.html`, On This Day pages, and `archive/entries/location-index.json`

3. **View the site**  
   Opening index.html in your browser will work but some features like the photos opening in a lighbox with prev/next, the map may not work as expected from the file:// protocol

   For all the features serve the generated archive and open it in the browser using:

   ```bash
   python launch.py
   ```

   This serves the `archive/` directory at `http://127.0.0.1:8000` and opens `index.html`.


## Keyboard shortcuts

When viewing the generated archive in your browser (served with `python launch.py`), the following keyboard shortcuts are available:

- **← / →** — Arrow keys navigate to the previous/next entry (when viewing an entry)
- **Esc** — Close photo lightbox overlays
- **Space** — Open the Menu on an entry page when menu button is in viewport (Up and down arrows select menu items)

Shortcuts work in most major browsers when the archive is served locally at `http://127.0.0.1:8000`. Some features (like lightbox navigation) may not work if you open HTML files directly from disk (`file://`), so use `python launch.py` for best results.




## Project structure

```text
Day One to Static Site/
├── generate.py              # Main script: pick ZIP → import → generate HTML
├── launch.py                # Serve archive/ on port 8000 and open browser
├── requirements.txt
├── generator/               # Core generation logic
│   ├── __init__.py
│   ├── archive_paths.py     # Date keys, paths, prev/next from manifest
│   ├── calendar_html.py     # archive/calendar.html
│   ├── entry_html.py        # Per-entry HTML (Jinja)
│   ├── entry_json.py        # Per-entry JSON from Day One export
│   ├── entry_helpers.py     # Title, location, place name helpers
│   ├── index_html.py        # archive/index.html (list by month)
│   ├── location_index.py    # entries/location-index.json for map
│   ├── manifest.py          # entries/manifest.json (UUID → date_key, path)
│   ├── media_html.py        # archive/media.html + entries/photo-index.json
│   ├── otd_html.py          # entries/on-this-day/MM-DD.html
│   ├── text_to_html.py      # Markdown → HTML, photo resolution
│   ├── zip_handler.py       # File picker + unzip
│   └── templates/           # Jinja: base, entry, list, calendar, media, on_this_day
├── utils/                   # Helpers for partial/full regeneration
│   ├── generate_again.py    # Full regen from all _imports/ subfolders
│   ├── generate_calendar.py
│   ├── generate_index.py    # Regenerate only index.html
│   ├── generate_map.py
│   ├── generate_otd.py
│   └── cleaner.py
├── archive/                 # Generated static site (git-ignored entries/*)
│   ├── index.html
│   ├── calendar.html
│   ├── media.html
│   ├── map.html
│   ├── assets/              # CSS, JS
│   └── entries/
│       ├── manifest.json
│       ├── location-index.json
│       ├── photo-index.json
│       ├── on-this-day/     # MM-DD.html
│       └── YYYY/MM/         # date_key.html, date_key.json, photos/
└── _imports/                # Extracted ZIPs (one folder per import)
```

## Output (archive/)

| Path | Description |
|------|-------------|
| `index.html` | List of entries by month with previews. |
| `calendar.html` | Calendar grid with links (and optional thumbnails) per day. |
| `media.html` | All photos in a grid; uses `entries/photo-index.json` for navigation. |
| `map.html` | Leaflet map of entries that have lat/lng; uses `entries/location-index.json`. |
| `entries/manifest.json` | One row per entry: `[uuid, date_key, html_path, creation_date]`. |
| `entries/YYYY/MM/<date_key>.html` | Single entry page. |
| `entries/YYYY/MM/<date_key>.json` | Raw entry JSON from Day One. |
| `entries/on-this-day/MM-DD.html` | Entries for that calendar day (all years). |

Date keys are `YYYY-MM-DD` or `YYYY-MM-DD_N` when multiple entries share the same local date (timezone comes from the entry’s `location.timeZoneName`).

## Utility scripts

Run from the project root. Some assume you’ve already run `generate.py` at least once (so `archive/entries/manifest.json` and entry JSONs exist).

| Script | Purpose |
|--------|---------|
| `utils/generate_again.py` | Regenerate the full archive from all folders in `_imports/` (no ZIP picker). Use after adding more exports or changing generator code. |
| `utils/generate_index.py` | Regenerate only `archive/index.html` from the current manifest. |
| `utils/generate_calendar.py` | Regenerate only `archive/calendar.html`. |
| `utils/generate_map.py` | Regenerate only `archive/entries/location-index.json` (and any map-specific output). |
| `utils/generate_otd.py` | Regenerate only the On This Day pages under `archive/entries/on-this-day/`. |

## Customization

- **Site title** — The templates use “The Narrative” as the site title and in the header; edit the Jinja templates in `generator/templates/` (e.g. `base.html`) to change it.
- **Place names** — `generate.py` can normalize place names in the imported JSON (e.g. `"Sanis"` → `"SANI's"`). Adjust `_normalize_import_json_place_names()` in `generate.py` for your own corrections.
- **Styling** — CSS lives under `archive/assets/css/` (e.g. `site.css`, `index.css`, `calendar.css`, `media.css`). Regeneration does not overwrite the whole `archive/` tree except for generated HTML/JSON; keep custom CSS in `archive/assets/` or adjust the generator to copy from a source folder.

## License

Licensed under the [MIT License](https://opensource.org/licenses/MIT)
