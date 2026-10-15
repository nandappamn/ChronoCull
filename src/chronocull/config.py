"""Configuration constants and supported file types for ChronoCull."""

import os
from pathlib import Path
from typing import Optional, Set


def load_dotenv(env_path: Optional[Path] = None) -> None:
    """Lightweight, zero-dependency .env file loader for ChronoCull.

    Searches cwd and repository root. Populates os.environ without overwriting
    existing shell environment variables.
    """
    if env_path is None:
        candidates = [
            Path.cwd() / ".env",
            Path(__file__).resolve().parent.parent.parent / ".env",
        ]
        for candidate in candidates:
            if candidate.is_file():
                env_path = candidate
                break

    if not env_path or not env_path.is_file():
        return

    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if key in os.environ:
                continue
            val = val.strip()
            if len(val) >= 2 and (
                (val.startswith('"') and val.endswith('"'))
                or (val.startswith("'") and val.endswith("'"))
            ):
                val = val[1:-1]
            os.environ[key] = val
    except Exception:
        pass


# Automatically load .env into os.environ on config import
load_dotenv()

IMAGE_EXTENSIONS: Set[str] = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".tiff",
    ".tif",
    ".webp",
    ".dng",
    ".cr2",
    ".cr3",
    ".nef",
    ".arw",
}

VIDEO_EXTENSIONS: Set[str] = {
    ".mov",
    ".mp4",
    ".m4v",
    ".avi",
    ".mkv",
    ".3gp",
}

SUPPORTED_EXTENSIONS: Set[str] = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

MANIFEST_FILENAME: str = "trip_manifest.json"
DEFAULT_OUTPUT_DIRNAME: str = "output"

TIMESTAMP_FORMAT: str = "%Y%m%d_%H%M%S"


def resolve_output_dir(
    folder_path: Path, output_dir_arg: Optional[str] = None
) -> Path:
    """Resolve destination directory for exported media and story artifacts."""
    if output_dir_arg:
        return Path(output_dir_arg).expanduser().resolve()

    # Search for project repository root (containing .git or pyproject.toml)
    curr = Path.cwd().resolve()
    repo_root = None
    for p in [curr] + list(curr.parents):
        if (p / ".git").exists() or (p / "pyproject.toml").exists():
            repo_root = p
            break

    base = (
        repo_root / DEFAULT_OUTPUT_DIRNAME
        if repo_root
        else curr / DEFAULT_OUTPUT_DIRNAME
    )
    return (base / folder_path.name).resolve()

# --- AI & Vision Services ---
GEMINI_API_KEY: Optional[str] = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_BASE_URL: str = os.environ.get(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta/models",
)

# --- Web Enrichment (Apify) ---
APIFY_TOKEN: Optional[str] = os.environ.get("APIFY_TOKEN")
APIFY_API_BASE: str = os.environ.get("APIFY_API_BASE", "https://api.apify.com/v2")
APIFY_ACTOR_PLACES: str = os.environ.get(
    "APIFY_ACTOR_PLACES", "compass/crawler-google-places"
)

# --- Geocoding & Nominatim ---
NOMINATIM_BASE_URL: str = os.environ.get(
    "NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org/reverse"
)
NOMINATIM_USER_AGENT: str = os.environ.get(
    "NOMINATIM_USER_AGENT", "ChronoCull/1.0 (travel-photo-curation)"
)

# --- System & Cache Paths ---
CACHE_DIR: Path = (
    Path(os.environ["CHRONOCULL_CACHE_DIR"]).expanduser().resolve()
    if os.environ.get("CHRONOCULL_CACHE_DIR")
    else Path.home() / ".cache" / "chronocull"
)
EXIFTOOL_PATH: Optional[str] = os.environ.get("EXIFTOOL_PATH")

