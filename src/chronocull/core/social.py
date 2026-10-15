"""Zero-copy social staging pipeline and post pack generation.

Exports ready-to-post folder structures (01_Carousel_Picks, 02_Stories_Vertical,
03_B_Roll_Extras, and _Rejected_Blur_And_Bursts) using OS hardlinks, relative
symlinks, or copies. Generates captions.txt and story_overlays.txt.
"""

import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chronocull.core.clustering import TripClusterResult, TripDay
from chronocull.models import MediaItem

logger = logging.getLogger("chronocull.social")


def link_or_copy_file(src: Path, dst: Path, mode: str = "auto") -> str:
    """Link or copy a file from src to dst.

    Modes:
        - 'auto': Attempts hardlink, falls back to relative symlink, falls back to copy.
        - 'hard': Hardlink only.
        - 'symlink': Relative symlink only.
        - 'copy': Full byte copy.

    Returns:
        The method used: 'hardlink', 'symlink', or 'copy'.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        dst.unlink()

    src_resolved = src.resolve()

    if mode == "auto":
        # 1. Try hardlink (same filesystem volume, zero extra bytes)
        try:
            os.link(src_resolved, dst)
            return "hardlink"
        except OSError:
            pass

        # 2. Try relative symlink
        try:
            rel_src = os.path.relpath(src_resolved, dst.parent)
            os.symlink(rel_src, dst)
            return "symlink"
        except OSError:
            pass

        # 3. Fallback to copy
        shutil.copy2(src_resolved, dst)
        return "copy"

    elif mode == "hard":
        os.link(src_resolved, dst)
        return "hardlink"

    elif mode == "symlink":
        rel_src = os.path.relpath(src_resolved, dst.parent)
        os.symlink(rel_src, dst)
        return "symlink"

    elif mode == "copy":
        shutil.copy2(src_resolved, dst)
        return "copy"

    else:
        raise ValueError(f"Unknown link mode: {mode}. Must be 'auto', 'hard', 'symlink', or 'copy'.")


def sanitize_filename(name: str) -> str:
    """Sanitize string for safe cross-platform folder naming."""
    clean = re.sub(r"[^\w\s-]", "", name).strip()
    return re.sub(r"[-\s]+", "_", clean)


def _resolve_item_file(item: MediaItem, candidate_dirs: List[Path]) -> Optional[Path]:
    """Resolve actual file on disk for a MediaItem across potential source directories."""
    candidates = []
    if item.target_path:
        candidates.append(item.target_path)
    if item.original_path:
        candidates.append(item.original_path)

    for c in list(candidates):
        if c.is_file():
            return c.resolve()

    for d in candidate_dirs:
        for c in candidates:
            p = d / c.name
            if p.is_file():
                return p.resolve()
            p2 = d / c
            if p2.is_file():
                return p2.resolve()

    return None


def generate_day_social_captions(day: TripDay) -> str:
    """Generate 3 distinct social caption vibes for the day's carousel post."""
    cities = []
    countries = []
    stop_titles = []

    for s in day.stops:
        city = s.location.get("city")
        country = s.location.get("country")
        if city and city not in cities:
            cities.append(city)
        if country and country not in countries:
            countries.append(country)
        if s.title and s.title not in stop_titles:
            stop_titles.append(s.title)

    primary_city = cities[0] if cities else "The Journey"
    primary_country = countries[0] if countries else ""
    loc_display = f"{primary_city}, {primary_country}".strip(", ")

    # Vibe 1: Casual 1-liner
    vibe_1 = f"Postcards from {primary_city} — chasing golden light and unforgettable moments."

    # Vibe 2: Micro-blog bullet list of venues & stops
    bullets = []
    for s in day.stops:
        t_str = f"{s.start_time.strftime('%H:%M')}"
        bullets.append(f"• {t_str} — {s.title} ({s.sun_phase.replace('_', ' ').title()})")
    vibe_2 = f"Day {day.day_number} in {loc_display} 📍\n" + "\n".join(bullets)

    # Vibe 3: Short punchy hook with location & hashtags
    tags = [f"#{sanitize_filename(primary_city)}", "#TravelDiaries", "#Wanderlust", "#ShotOniPhone", "#ChronoCull"]
    if primary_country:
        tags.insert(1, f"#{sanitize_filename(primary_country)}")
    vibe_3 = f"Unfiltered {primary_city}.\n\n📍 {loc_display}\n{' '.join(tags)}"

    return (
        f"================================================================================\n"
        f"CHRONOCULL SOCIAL PACK — DAY {day.day_number:02d} ({day.date})\n"
        f"Location: {loc_display}\n"
        f"================================================================================\n\n"
        f"[VIBE 1: CASUAL ONE-LINER]\n"
        f"{vibe_1}\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"[VIBE 2: MICRO-BLOG ROUTE & VENUES]\n"
        f"{vibe_2}\n\n"
        f"--------------------------------------------------------------------------------\n"
        f"[VIBE 3: PUNCHY SOCIAL HOOK & HASHTAGS]\n"
        f"{vibe_3}\n"
        f"================================================================================\n"
    )


def generate_story_overlays(day: TripDay, story_items: List[Tuple[str, MediaItem]]) -> str:
    """Generate punchy 3-5 word text hooks per vertical story slide."""
    lines = [
        f"CHRONOCULL STORY OVERLAYS — DAY {day.day_number:02d} ({day.date})",
        "=" * 60,
    ]
    for slide_name, item in story_items:
        time_str = item.timestamp.strftime("%H:%M")
        sun = item.metadata.get("sun_phase", "").replace("_", " ")
        if sun:
            hook = f"Golden hour magic at {time_str}" if "golden" in sun else f"Exploring at {time_str}"
        else:
            hook = f"Moments from {time_str}"
        lines.append(f"{slide_name}: \"{hook}\"")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"


def _item_quality_score(item: MediaItem) -> float:
    """Calculate ranking score for carousel curation."""
    score = 0.0
    meta = item.metadata

    # 1. AI aesthetic score (1-10)
    if "ai_curation" in meta and isinstance(meta["ai_curation"], dict):
        score += float(meta["ai_curation"].get("aesthetic_score", 5)) * 2.0

    # 2. Hero candidate nomination
    if meta.get("is_hero_candidate", False):
        score += 8.0

    # 3. Sharpness variance
    sharpness = meta.get("sharpness_score", 0.0)
    if sharpness > 100.0:
        score += min(5.0, sharpness / 100.0)

    # 4. Colorfulness
    colorfulness = meta.get("colorfulness", 0.0)
    if colorfulness > 30.0:
        score += min(3.0, colorfulness / 20.0)

    # 5. Aspect ratio preference for Carousels (4:5 and 1:1 preferred)
    fmt = meta.get("social_format")
    if fmt == "carousel_4_5":
        score += 3.0
    elif fmt == "square_1_1":
        score += 2.0

    return score


def export_social_bundles(
    cluster_result: TripClusterResult,
    output_dir: Path,
    candidate_dirs: Optional[List[Path]] = None,
    link_mode: str = "auto",
) -> Dict[str, Any]:
    """Export zero-copy social bundles partitioned into Carousel Picks, Stories, B-Roll, and Rejects."""
    output_dir.mkdir(parents=True, exist_ok=True)
    dirs = candidate_dirs or []

    stats: Dict[str, Any] = {
        "output_dir": str(output_dir),
        "days": [],
        "total_carousel_picks": 0,
        "total_stories": 0,
        "total_b_roll": 0,
        "total_rejected": 0,
        "link_methods_used": {},
    }

    rejected_dir = output_dir / "_Rejected_Blur_And_Bursts"
    all_rejected_items: List[MediaItem] = []

    def record_link(m: str):
        stats["link_methods_used"][m] = stats["link_methods_used"].get(m, 0) + 1

    for day in cluster_result.days:
        # Determine day folder name: Day_01_City_SunPhase
        day_locs = [s.location.get("city") for s in day.stops if s.location.get("city")]
        primary_city = day_locs[0] if day_locs else "Stop"
        first_sun = day.stops[0].sun_phase if day.stops else "day"
        day_folder_name = f"Day_{day.day_number:02d}_{sanitize_filename(primary_city)}_{sanitize_filename(first_sun)}"
        day_dir = output_dir / day_folder_name

        carousel_dir = day_dir / "01_Carousel_Picks"
        stories_dir = day_dir / "02_Stories_Vertical"
        broll_dir = day_dir / "03_B_Roll_Extras"

        # Separate items for this day
        day_items: List[MediaItem] = []
        for s in day.stops:
            day_items.extend(s.items)

        # De-duplicate references if items shared across stops
        seen_ids = set()
        unique_day_items = []
        for it in day_items:
            iid = id(it)
            if iid not in seen_ids:
                seen_ids.add(iid)
                unique_day_items.append(it)

        # Partition into rejected vs valid
        valid_items: List[MediaItem] = []
        for it in unique_day_items:
            meta = it.metadata
            is_reject = False

            if meta.get("is_reject", False):
                is_reject = True
            elif "ai_curation" in meta and meta["ai_curation"].get("is_reject", False):
                is_reject = True
            elif meta.get("is_burst_duplicate", False):
                is_reject = True
            elif meta.get("is_blurry", False) and not meta.get("is_hero_candidate", False):
                is_reject = True

            if is_reject:
                all_rejected_items.append(it)
            else:
                valid_items.append(it)

        # Rank valid items for Carousel Picks (top 5-10)
        ranked_items = sorted(valid_items, key=_item_quality_score, reverse=True)
        carousel_picks = ranked_items[:10]
        carousel_set = set(id(it) for it in carousel_picks)

        # Vertical media for Stories
        vertical_candidates = [
            it for it in valid_items
            if it.metadata.get("orientation") == "vertical"
            or it.metadata.get("social_format") in ("story_9_16", "carousel_4_5")
            or (it.media_type == "video" and it.metadata.get("duration_seconds", 0) <= 30)
        ]
        # Pick up to 8 vertical stories
        stories_picks = vertical_candidates[:8]
        stories_set = set(id(it) for it in stories_picks)

        # B-Roll is everything else valid
        b_roll_picks = [it for it in valid_items if id(it) not in carousel_set and id(it) not in stories_set]

        # 1. Stage Carousel Picks
        carousel_staged = 0
        for idx, it in enumerate(carousel_picks, start=1):
            src_file = _resolve_item_file(it, dirs)
            if src_file:
                prefix = "HERO" if idx == 1 or it.metadata.get("is_hero_candidate") else "PICK"
                dst_name = f"{idx:02d}_{prefix}_{src_file.name}"
                method = link_or_copy_file(src_file, carousel_dir / dst_name, mode=link_mode)
                record_link(method)
                carousel_staged += 1

        # Write captions.txt
        captions_content = generate_day_social_captions(day)
        carousel_dir.mkdir(parents=True, exist_ok=True)
        (carousel_dir / "captions.txt").write_text(captions_content, encoding="utf-8")

        # 2. Stage Stories
        stories_staged = []
        for idx, it in enumerate(stories_picks, start=1):
            src_file = _resolve_item_file(it, dirs)
            if src_file:
                dst_name = f"story_{idx:02d}_{src_file.name}"
                method = link_or_copy_file(src_file, stories_dir / dst_name, mode=link_mode)
                record_link(method)
                stories_staged.append((dst_name, it))

        # Write story_overlays.txt
        stories_dir.mkdir(parents=True, exist_ok=True)
        overlays_content = generate_story_overlays(day, stories_staged)
        (stories_dir / "story_overlays.txt").write_text(overlays_content, encoding="utf-8")

        # 3. Stage B-Roll Extras
        broll_staged = 0
        for it in b_roll_picks:
            src_file = _resolve_item_file(it, dirs)
            if src_file:
                method = link_or_copy_file(src_file, broll_dir / src_file.name, mode=link_mode)
                record_link(method)
                broll_staged += 1

        stats["total_carousel_picks"] += carousel_staged
        stats["total_stories"] += len(stories_staged)
        stats["total_b_roll"] += broll_staged
        stats["days"].append({
            "day": day.day_number,
            "folder": day_folder_name,
            "carousel_picks": carousel_staged,
            "stories": len(stories_staged),
            "b_roll": broll_staged,
        })

    # Stage Rejected items into _Rejected_Blur_And_Bursts
    rejected_staged = 0
    if all_rejected_items:
        rejected_dir.mkdir(parents=True, exist_ok=True)
        for it in all_rejected_items:
            src_file = _resolve_item_file(it, dirs)
            if src_file:
                dst_path = rejected_dir / src_file.name
                if not dst_path.exists():
                    method = link_or_copy_file(src_file, dst_path, mode=link_mode)
                    record_link(method)
                    rejected_staged += 1

    stats["total_rejected"] = rejected_staged
    logger.info(f"Staged {stats['total_carousel_picks']} carousel picks, {stats['total_stories']} stories, {stats['total_rejected']} rejects to {output_dir}")
    return stats

