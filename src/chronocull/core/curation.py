"""Multimodal AI Curation & Storytelling pipeline (Phase 2)."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from chronocull.core.clustering import TripClusterResult
from chronocull.core.vlm_client import GeminiClient

logger = logging.getLogger("chronocull.curation")


def curate_trip(
    cluster_result: TripClusterResult,
    folder_path: Path,
    source_folder: Optional[Path] = None,
) -> str:
    """Run Phase 2 curation: score photos, tag scenes, and generate travelogue."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not found. Skipping Phase 2 AI curation.")
        return ""

    client = GeminiClient(api_key=api_key)

    # 1. Visual Quality Scoring & Scene Captioning
    total_analyzed = 0
    for day in cluster_result.days:
        for stop in day.stops:
            # To save costs and time, we only analyze heuristic 'hero' candidates or standalone items.
            candidates = [it for it in stop.items if it.metadata.get("is_hero_candidate", False) or stop.burst_groups_count == 0]
            # If still too many, just pick up to 3 per stop for narrative context
            candidates = candidates[:3]

            for item in candidates:
                if item.media_type != "image":
                    continue
                
                target_path = item.target_path or item.original_path
                candidates_paths = [
                    folder_path / target_path,
                    folder_path / item.original_path,
                    item.original_path,
                ]
                if source_folder:
                    candidates_paths.append(source_folder / item.original_path)
                    candidates_paths.append(source_folder / item.original_name)

                full_path = None
                for p in candidates_paths:
                    if p.exists() and p.is_file():
                        full_path = p
                        break

                if full_path:
                    logger.info(f"Analyzing image: {full_path.name}...")
                    try:
                        analysis = client.analyze_image(full_path)
                        item.metadata["ai_curation"] = analysis
                        total_analyzed += 1
                    except Exception as e:
                        logger.error(f"Failed to analyze {full_path.name}: {e}")

    logger.info(f"Successfully scored and captioned {total_analyzed} images.")

    # 2. Narrative Synthesis
    # Prepare a condensed JSON representation for the LLM context
    trip_summary = {
        "summary": {
            "total_days": len(cluster_result.days),
            "total_stops": cluster_result.total_stops
        },
        "days": []
    }

    for day in cluster_result.days:
        day_dict = {"day": day.day_number, "date": day.date, "stops": []}
        for stop in day.stops:
            stop_dict = {
                "title": stop.title,
                "time": f"{stop.start_time.strftime('%H:%M')} - {stop.end_time.strftime('%H:%M')}",
                "context": stop.apify_context,
                "highlights": []
            }
            # Add AI captions from analyzed photos
            for item in stop.items:
                if "ai_curation" in item.metadata:
                    stop_dict["highlights"].append(item.metadata["ai_curation"])
            
            day_dict["stops"].append(stop_dict)
        trip_summary["days"].append(day_dict)

    logger.info("Synthesizing narrative travelogue...")
    travelogue_md = client.generate_travelogue(json.dumps(trip_summary, indent=2))
    
    out_path = folder_path / "TRAVELOGUE.md"
    out_path.write_text(travelogue_md, encoding="utf-8")
    logger.info(f"Travelogue written to {out_path.name}")
    
    return travelogue_md

