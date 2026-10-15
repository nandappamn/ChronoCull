# ChronoCull

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Clean](https://img.shields.io/badge/architecture-src--layout-green.svg)](#repository-structure)

**ChronoCull** is an intelligent media curation pipeline that transforms disorganized trip photos and videos into structured, chronologically sorted, geotagged, clustered travelogues, and ready-to-post social media packs.

---

## ⚡ Key Capabilities

* **Multi-Tier Capture Timestamp Resolution**:
  * Tier 1: EXIF sub-IFD tags (`DateTimeOriginal`, `SubSecTimeOriginal`).
  * Tier 2: ISOBMFF QuickTime / MP4 `moov.mvhd` atom header parser for videos.
  * Tier 3: Date regex patterns (e.g. `YYYYMMDD_HHMMSS`, WhatsApp, Camera exports).
  * Tier 4: macOS Spotlight (`kMDItemContentCreationDate`).
  * Tier 5: Non-destructive filesystem birthtime/mtime fallback.
* **Safe, Atomic Operations**:
  * **Dry-Run by Default**: Review full rename plans with Rich visual tables or JSON output before touching any files.
  * **Atomic Staging**: Uses UUID intermediate renames to prevent partial state or collision overwrites.
  * **Complete Rollback**: Generates `trip_manifest.json` enabling one-command rollback across nested subdirectories.
* **Offline Reverse Geocoding**:
  * 100% offline 3D unit-sphere `scipy.spatial.KDTree` geocoding using a bundled dataset of world cities (`data/cities.json.gz`).
  * Great-circle Haversine distance computations with optional cached Nominatim lookup.
* **Spatiotemporal Clustering & Curation**:
  * **Temporal Proximity GPS Interpolation**: Resolves missing GPS coordinates for DSLR/action cameras taken contemporaneously with mobile photos.
  * **Day & Stop Segmentation**: Clusters media based on elapsed time and spatial distance.
  * **Visual Heuristics**: 64-bit DCT perceptual hash (pHash/dHash), Laplacian variance blur detection ($\text{Var}(\nabla^2 I)$), opportunistic video keyframe extraction via `ffmpeg`, aspect ratio / orientation classification (9:16 vertical stories, 4:5 carousels, 1:1 squares, 16:9 landscape), and burst hero candidate selection.
  * **Export Artifacts**: Emits `trip_manifest_v2.json`, `trip_route.geojson`, and editorial `travel_album.html`.
* **Zero-Copy Social Media Staging (`--export-social`)**:
  * Segregates curated trip media into ready-to-post folder bundles (`01_Carousel_Picks/`, `02_Stories_Vertical/`, `03_B_Roll_Extras/`, and `_Rejected_Blur_And_Bursts/`).
  * Emits `captions.txt` (3 distinct vibes: casual 1-liner, micro-blog itinerary, punchy hook with tags) and `story_overlays.txt`.
  * Zero disk space overhead via OS hardlinks (`auto`), relative symlinks, or file copies (`--link-mode`).
* **Multimodal AI Curation & Storytelling (Phase 2)**:
  * **VLM Quality & Aesthetic Scoring**: Evaluates composition, lighting, emotional engagement (scores 1–10), filters blurry/pocket shots (`is_reject`), and extracts semantic scene tags with 1-sentence captions via Google Gemini.
  * **Narrative Travelogue Synthesis**: Connects trip itinerary, POI context, and photo captions into a rich chronological Markdown story (`TRAVELOGUE.md`).
  * **Apify POI Web Enrichment**: Integrates with Apify actors (e.g. `compass/crawler-google-places`) to enrich stops with venue descriptions, Google ratings, addresses, and top reviews.
  * **Responsive Visual Showcase**: Generates an editorial, publication-grade responsive HTML photo journal (`travel_album.html`) with inline styling and zero external runtime dependencies.

---

## 📁 Repository Structure

```text
ChronoCull/
├── README.md                      # Project documentation & quickstart
├── AGENTS.md                      # AI agent operating principles & Karpathy disciplines
├── pyproject.toml                 # Modern PEP 621 packaging & CLI entrypoint
├── requirements.txt               # Pinned dependencies
├── pytest.ini                     # Pytest configuration (pythonpath = src)
├── .gitignore                     # Git ignore rules (excludes large media & caches)
│
├── src/
│   └── chronocull/                # Core application package
│       ├── __init__.py            # Package exports and version
│       ├── __main__.py            # Module entrypoint (python -m chronocull)
│       ├── cli.py                 # CLI interface & argument parsing
│       ├── config.py              # Constants, supported extensions & regexes
│       ├── models.py              # Strongly-typed MediaItem & cluster dataclasses
│       │
│       ├── core/                  # Processing pipeline
│       │   ├── extractor.py       # Multi-tier EXIF, video, and OS metadata engine
│       │   ├── sorter.py          # Chronological sorting & collision-free naming
│       │   ├── renamer.py         # 2-phase atomic renames & rollback engine
│       │   ├── clustering.py      # Day/Stop spatiotemporal clustering
│       │   ├── social.py          # Zero-copy social staging & caption pack generation
│       │   ├── browser_staging.py # Optional browser-use staging assistant
│       │   ├── manifest.py        # v1 JSON manifest persistence (trip_manifest.json)
│       │   ├── story_manifest.py  # v2 Story manifest & GeoJSON route export
│       │   ├── curation.py        # Multimodal AI curation & TRAVELOGUE.md synthesis
│       │   ├── enricher.py        # Web enrichment client (Google Places)
│       │   ├── vlm_client.py      # Zero-dependency Gemini VLM REST client
│       │   └── html_showcase.py   # Responsive editorial HTML photo album generator
│       │
│       ├── utils/                 # Utilities & algorithms
│       │   ├── geocoder.py        # 3D KDTree offline reverse geocoder
│       │   └── heuristics.py      # pHash, dHash, blur detection & color scoring
│       │
│       └── data/                  # Packaged static assets
│           └── cities.json.gz     # Bundled world cities KDTree dataset
│
├── tests/                         # Automated test suite (13 test modules, 46 tests)
├── docs/                          # Architecture blueprints & framework specifications
├── services/                      # Companion microservices (freellm-gateway)
├── .env.example                   # Environment configuration template
├── .agents/                       # Modular agent skills & verification harness
└── .agent-memory/                 # Agent architectural decision history
```

---

## 🚀 Quick Start

### 1. Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/nandappamn/ChronoCull.git
cd ChronoCull

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
pip install -e .

# Optional: Install browser staging or enrichment extras
pip install -e ".[agent]"   # For browser-use & Playwright
pip install -e ".[apify]"   # For Apify remote enrichment
```

### 2. Basic & Advanced Usage

#### Preview Renaming Plan (Safe Dry-Run)
```bash
chronocull /path/to/trip_photos
```

#### Apply Renaming on Disk
```bash
chronocull /path/to/trip_photos --apply
```

#### Cluster Media into Days, Stops & Select Burst Heroes
```bash
chronocull /path/to/trip_photos --cluster
```

#### Export Zero-Copy Social Media Packs (Instagram Ready)
```bash
# Creates 01_Carousel_Picks, 02_Stories_Vertical, captions.txt, and story_overlays.txt
chronocull /path/to/trip_photos --export-social
```

#### Export Journey Route & Visual Showcase Album
```bash
# Exports trip_manifest_v2.json, trip_route.geojson, and travel_album.html
chronocull /path/to/trip_photos --export-story
```

#### Run Multimodal AI Curation (Gemini VLM & TRAVELOGUE.md)
```bash
chronocull /path/to/trip_photos --cluster --curate-ai
```

#### Rollback Renamed Files
```bash
chronocull /path/to/trip_photos --rollback
```

---

## 🧪 Testing & Verification

Run the automated test suite (46 tests across unit and integration suites):

```bash
pytest
```

Run agent harness and structural verification:

```bash
python .agents/skills/harness-engineering/scripts/verify_harness.py
```

---

## 🤖 AI Agent Harness

This repository is governed by the principles in [`AGENTS.md`](AGENTS.md), adhering to **Andrej Karpathy's Disciplined Agent Principles**:
1. **Think Before Coding**: Surface assumptions and clarify ambiguity first.
2. **Simplicity First**: Minimum code that solves the problem.
3. **Surgical Changes**: Restrict diffs strictly to the goal.
4. **Goal-Driven Execution**: Closed-loop validation with automated verification.

---

## 📄 License

MIT License. See `LICENSE` for details.
