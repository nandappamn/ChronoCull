# ChronoCull — Master Architecture & Implementation Plan

> **System Purpose**: An autonomous, intelligent media curation pipeline that transforms disorganized trip photos and videos into structured, chronologically sorted, geotagged, and AI-curated travelogues.

---

## 1. Executive Summary & Phased Roadmap

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             ChronoCull Pipeline                              │
├─────────────────────┬──────────────────────────┬────────────────────────────┤
│ Phase 0 (Complete)  │ Phase 1 (Complete)       │ Phase 2 (Complete)         │
│ Ingestion & Metadata│ Geocoding & Clustering   │ Multimodal AI Curation     │
│ Chronological Sort  │ Stop / Landmark Detection│ Visual Aesthetic Ranking   │
│ Safe Atomic Rename  │ Perceptual Hashing       │ Travelogue & Story Export  │
└─────────────────────┴──────────────────────────┴────────────────────────────┘
```

| Phase | Milestone | Scope & Deliverables | Status |
| :--- | :--- | :--- | :--- |
| **Phase 0** | **Media Ingestion & Normalization** | Multi-tier metadata extraction (EXIF, QuickTime atoms, regex, OS metadata), chronological sorting, collision-free naming, dry-run simulation, two-phase atomic disk renaming, manifest tracking (`trip_manifest.json`), and rollback. | **Completed & Verified** |
| **Phase 1** | **Geocoding & Spatiotemporal Clustering** | Decimal GPS conversion & EXIF optics extraction, offline KDTree 3D unit sphere reverse geocoding, temporal GPS interpolation ("Missing GPS"), Day & Stop clustering, perceptual hashing (pHash/dHash), Laplacian blur ranking, burst hero selection, `trip_manifest_v2.json`, and `trip_route.geojson`. | **Completed & Verified** |
| **Phase 2** | **Multimodal AI Curation & Storytelling** | VLM-based aesthetic and semantic quality scoring, highlight selection, automated narrative travelogue synthesis (`TRAVELOGUE.md`), Apify POI web enrichment, and interactive HTML album export (`travel_album.html`). | **Completed & Verified** |

---

## 2. Phase 0: Media Ingestion, Extraction & Normalization (Implemented)

### Core Objectives
1. **Never lose or corrupt data**: Non-destructive, dry-run default with atomic two-phase renames and complete reversibility (`--rollback`).
2. **Deterministic chronological ordering**: Robust capture timestamp resolution using a 5-tier fallback hierarchy.
3. **Collision-free standardized naming**: Format as `YYYYMMDD_HHMMSS_<original_name>.<ext>`, preserving camera prefixes and original names for auditability.
4. **Idempotency & pairing preservation**: Strip existing timestamps cleanly without double-prefixing; preserve Apple Live Photo (`.heic` + `.mov`) pairings.

### Architecture & Fallback Tiering
```text
Raw Photo / Video File
         │
         ▼
┌──────────────────────────────────────────────┐
│ Tier 1: External exiftool (if present)       │
└──────────────────────┬───────────────────────┘
                       │ (if unavailable or missing tags)
                       ▼
┌──────────────────────────────────────────────┐
│ Tier 2: Pure-Python Parsers                  │
│  • Pillow EXIF IFD / SubIFD (Images)         │
│  • ISOBMFF QuickTime Atom Box Parser (Videos)│
└──────────────────────┬───────────────────────┘
                       │ (if no embedded capture date)
                       ▼
┌──────────────────────────────────────────────┐
│ Tier 3: Filename Regex Pattern Matching      │
│  • Matches YYYYMMDD_HHMMSS, WhatsApp, etc.  │
└──────────────────────┬───────────────────────┘
                       │ (if filename has no date)
                       ▼
┌──────────────────────────────────────────────┐
│ Tier 4: macOS mdls Spotlight Metadata        │
│  • kMDItemContentCreationDate                │
└──────────────────────┬───────────────────────┘
                       │ (last resort fallback)
                       ▼
┌──────────────────────────────────────────────┐
│ Tier 5: Filesystem Stat Fallback             │
│  • st_birthtime (macOS) / st_mtime           │
└──────────────────────────────────────────────┘
```

### Key Modules in `src/chronocull/`
- [`config.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/config.py): Supported extensions, timestamp formats, and manifest filename constants.
- [`models.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/models.py): Strongly-typed `MediaItem` dataclass capturing path, media type, timestamps, sources, subsecond bursts, and raw device metadata.
- [`core/extractor.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/extractor.py): Multi-tier metadata parser for EXIF, QuickTime/MP4 `moov.mvhd` atoms, macOS `mdls`, and regex patterns.
- [`core/sorter.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/sorter.py): Strict chronological sorting, subsecond burst ordering, and idempotent naming with counter collision disambiguation (`_01`, `_02`).
- [`core/renamer.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/renamer.py): Dry-run Rich/ASCII table visualization, two-phase atomic renaming via UUID staging, and manifest-driven rollback.
- [`core/manifest.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/manifest.py): JSON serialization and deserialization of `trip_manifest.json`, storing both absolute and relative path mappings.
- [`cli.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/cli.py): CLI interface supporting `--apply`, `--rollback`, `-r/--recursive`, and `--json`.

### Production Edge Cases Resolved during `TEST_PHOTOS` Validation
1. **Recursive Subdirectory Rollback**: Manifest preserves `rel_original_path` and `rel_target_path` to support rollback across arbitrarily nested folders without orphan path mismatches.
2. **Compact 14-Digit Timestamp Idempotency**: Extended `TIMESTAMP_PREFIX_REGEX` to `^\d{8}[_]?\d{6}_` to strip legacy `YYYYMMDDHHMMSS_` prefixes alongside `YYYYMMDD_HHMMSS_`, preventing double-timestamping on pre-stamped collections.

---

## 3. Phase 1: Geocoding & Spatiotemporal Clustering (Implemented & Verified)

### Objectives
Transform the flat chronological sequence into a spatial, temporal, and visually pre-screened travel journey.

### Key Implemented Modules
1. **[`heuristics.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/utils/heuristics.py)**:
   - 64-bit DCT perceptual hash (pHash) and difference hash (dHash).
   - Fast Laplacian variance sharpness score $\text{Var}(\nabla^2 I)$ for motion blur filtering.
   - Exposure metrics (mean brightness, contrast, highlight/shadow clipping) and Hasler-Süsstrunk colorfulness scoring.
2. **[`geocoder.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/utils/geocoder.py)**:
   - 100% offline 3D unit sphere `scipy.spatial.KDTree` reverse geocoding with bundled world cities dataset (`data/cities.json.gz`).
   - Great-circle Haversine distance calculation in kilometers.
   - Optional rate-limited and cached OpenStreetMap Nominatim reverse geocoding for fine-grained landmarks.
3. **[`clustering.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/clustering.py)**:
   - **Temporal Proximity GPS Interpolation**: Resolves the "Missing GPS" problem by allowing camera photos taken within $\Delta t \le 30\text{ min}$ of a smartphone GPS photo to inherit coordinates.
   - **Trip Day Segmentation**: Splits days by calendar date and inactivity/sleep gaps ($> 6\text{ hours}$).
   - **Stop Clustering**: Groups media within $2.5\text{ km}$ and $3\text{ hours}$ into atomic trip activities.
   - **Sun Phase & Lighting Estimation**: Classifies lighting into `dawn`, `golden_hour`, `morning`, `midday`, `late_afternoon`, `sunset`, `blue_hour`, and `night`.
   - **Burst Grouping & Hero Selection**: Identifies near-duplicate bursts ($\Delta t \le 10\text{s}$, Hamming dist $\le 8$) and designates the sharpest photo as `burst_hero_candidate`.
4. **[`story_manifest.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/story_manifest.py)**:
   - Exports hierarchical `trip_manifest_v2.json` and standard `trip_route.geojson`.
5. **[`cli.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/cli.py)**:
   - Subcommands and flags: `--cluster`, `--export-story`, `--online-geocode`, `--no-heuristics`.
   - Rich terminal visualizer displaying the complete tree of Days $\to$ Stops $\to$ Locations $\to$ Hero Candidates.

---

## 4. Phase 2: Multimodal AI Curation & Travelogue Storytelling (Implemented & Verified)

### Objectives
Use multimodal vision models and external POI data to score media quality, filter rejects, caption scenes, enrich travel stops, and synthesize rich narrative travelogues and visual showcase albums.

### Key Implemented Modules in `src/chronocull/core/`
1. **[`enricher.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/enricher.py) (`ApifyEnricher`)**:
   - Zero-dependency client communicating with the Apify REST API using standard `urllib`.
   - Runs `compass/crawler-google-places` to query venue details based on stop titles and geocoded locations.
   - Enriches `TripStop` objects in-place with `apify_context`: description, Google rating, address, category, and top user reviews.
   - Invoked via `--enrich-apify` CLI flag.
2. **[`vlm_client.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/vlm_client.py) (`GeminiClient`)**:
   - Lightweight, zero-dependency REST client targeting Google Gemini Vision (`gemini-3.8-flash` or configurable via `GEMINI_MODEL`).
   - In-memory thumbnail downsampling (1024px Lanczos) and Base64 JPEG encoding to minimize network latency.
   - Structured JSON response extraction:
     - `aesthetic_score`: Integer (1–10) measuring composition, exposure, and emotion.
     - `is_reject`: Boolean flag identifying accidental pocket shots, excessive motion blur, or black frames.
     - `tags`: List of 2–4 semantic scene descriptors (e.g., `monument`, `sunset`, `street_food`).
     - `caption`: Concise 1-sentence descriptive caption.
   - Resilient retry loop with exponential backoff handling HTTP 429 and 503 throttling up to 12 attempts.
3. **[`curation.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/curation.py) (`curate_trip`)**:
   - Curates photos per stop, prioritizing burst hero candidates and representative images (up to 3 per stop) to optimize token efficiency.
   - Synthesizes trip context, timestamps, Apify place descriptions, and photo captions into a chronological Markdown travelogue (`TRAVELOGUE.md`).
   - Invoked via `--curate-ai` CLI flag.
4. **[`html_showcase.py`](file:///Users/sidhu-mac/Documents/PERSONAL_PROJECT/chronocull/src/chronocull/core/html_showcase.py) (`generate_html_showcase`)**:
   - Generates responsive, publication-grade editorial HTML photo album (`travel_album.html`) using pure Python f-strings and inline CSS.
   - Zero external frontend dependencies or heavy templating engines.
   - Formats Day sections, stop cards with timing/location/rating, and photo grids with AI captions and tags.
   - Automatically generated during `--export-story`.

---

## 5. Artifacts & Data Contracts

### 1. Phase 0 Manifest Schema (`trip_manifest.json`)
```json
{
  "version": "1.0",
  "generated_at": "2026-09-28T12:00:00.000000",
  "status": "applied",
  "folder_path": "/path/to/trip_folder",
  "summary": {
    "total_items": 902,
    "images_count": 902,
    "videos_count": 0,
    "sources": { "exif": 902 },
    "warnings_count": 0
  },
  "items": [
    {
      "original_name": "IMG_3425.JPG",
      "renamed_to": "20110801_170624_IMG_3425.JPG",
      "rel_original_path": "China Visit/IMG_3425.JPG",
      "rel_target_path": "China Visit/20110801_170624_IMG_3425.JPG",
      "timestamp": "2011-08-01T17:06:24",
      "timestamp_source": "exif",
      "media_type": "image",
      "subsecond": null,
      "metadata": { "make": "Canon", "model": "Canon PowerShot A3100 IS" }
    }
  ]
}
```

### 2. Phase 1 & 2 Story Manifest Schema (`trip_manifest_v2.json`)
```json
{
  "version": "2.0",
  "generated_at": "2026-10-09T00:45:00.000000",
  "folder_path": "/path/to/trip_folder",
  "trip_summary": {
    "date_range": { "start": "2024-07-15", "end": "2024-07-20" },
    "total_days": 5,
    "total_stops": 18,
    "total_items": 450,
    "gps_coverage": { "recorded": 380, "interpolated": 65, "none": 5 },
    "burst_groups_count": 22,
    "hero_candidates_count": 22,
    "cities_visited": ["Paris", "Versailles"],
    "countries_visited": ["France"]
  },
  "days": [
    {
      "day_number": 1,
      "date": "2024-07-15",
      "stops_count": 4,
      "total_items": 95,
      "stops": [
        {
          "stop_id": "D1_S1",
          "day_number": 1,
          "title": "Eiffel Tower",
          "time_window": {
            "start": "2024-07-15T09:30:00",
            "end": "2024-07-15T12:00:00",
            "duration_minutes": 150.0,
            "sun_phase": "morning"
          },
          "location": {
            "lat": 48.8584,
            "lon": 2.2945,
            "city": "Paris",
            "country": "France"
          },
          "transit_status": "dwell",
          "items_count": 35,
          "apify_context": {
            "source": "apify/compass/crawler-google-places",
            "title": "Eiffel Tower",
            "rating": 4.7,
            "description": "Iconic wrought-iron 19th-century tower."
          },
          "items": []
        }
      ]
    }
  ]
}
```

### 3. Route GeoJSON Contract (`trip_route.geojson`)
- **Point Features**: Geographic centroids for each stop including timing, duration, transit status, and city name.
- **LineString Features**: Sequential transit trajectories connecting stops with calculated Haversine distance (`distance_km`) and transit duration (`transit_time_minutes`).

### 4. Visual & Narrative Exports
- **`travel_album.html`**: Self-contained responsive HTML photo journal with CSS styling.
- **`TRAVELOGUE.md`**: Chronological markdown narrative synthesized by Gemini Vision.

---

## 6. Verification & Test Suite

The comprehensive pytest suite (11 test modules, 36 unit and integration tests) enforces complete regression prevention across all three pipeline phases:

| Module | Scope | Test Cases |
| :--- | :--- | :--- |
| **`test_extractor.py`** | Multi-tier metadata extraction (EXIF, QuickTime atoms, filename regex, macOS mdls, filesystem stat fallback). | 7 tests |
| **`test_sorter.py`** | Chronological ordering, subsecond burst sort, Live Photo pairing, and 14-digit prefix idempotency. | 5 tests |
| **`test_renamer.py`** | Dry-run simulation, two-phase atomic renaming via UUID staging, manifest tracking, and recursive rollback. | 2 tests |
| **`test_clustering.py`** | Spatiotemporal clustering, Day/Stop segmentation, temporal GPS interpolation, and burst detection. | 3 tests |
| **`test_geocoder.py`** | 3D KDTree unit-sphere reverse geocoding, Haversine distance, and cached Nominatim fallback. | 3 tests |
| **`test_heuristics.py`** | 64-bit DCT pHash/dHash, Laplacian blur variance $\text{Var}(\nabla^2 I)$, and colorfulness scoring. | 4 tests |
| **`test_story_manifest.py`** | Serialization of `trip_manifest_v2.json` and standard GeoJSON trajectory routes (`trip_route.geojson`). | 1 test |
| **`test_curation.py`** | Multimodal AI curation pipeline, VLM mock execution, and `TRAVELOGUE.md` generation. | 1 test |
| **`test_html_showcase.py`** | Responsive HTML showcase album rendering, stop cards, metadata formatting, and photo grid. | 1 test |
| **`test_config.py`** | Centralized configuration, zero-dependency `.env` parsing, and custom environment variable overrides. | 4 tests |
| **`test_cli.py`** | CLI integration, dry-run tables, `--json`, `--apply`, `--rollback`, `--cluster`, and `--export-story`. | 5 tests |
| **Total** | **Full Pipeline Automated Coverage** | **36 tests passed (<1s runtime)** |
