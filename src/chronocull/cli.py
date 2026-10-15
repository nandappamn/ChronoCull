import os

"""CLI interface for ChronoCull."""

import argparse
import json
import sys
from pathlib import Path
from typing import List

from chronocull import __version__
from chronocull.config import (
    MANIFEST_FILENAME,
    SUPPORTED_EXTENSIONS,
    load_dotenv,
    resolve_output_dir,
)
from chronocull.core.clustering import TripClusterResult, cluster_trip_journey
from chronocull.core.extractor import extract_media_item
from chronocull.core.renamer import apply_renames, print_dry_run_table, rollback_renames
from chronocull.core.sorter import sort_and_plan_media
from chronocull.core.story_manifest import export_trip_geojson, write_story_manifest
from chronocull.core.enricher import run_enrichment_pipeline
from chronocull.models import MediaItem


def scan_media_files(folder_path: Path, recursive: bool = False) -> List[Path]:
    """Scan folder for supported media files, ignoring hidden files and manifest."""
    files: List[Path] = []
    iterator = folder_path.rglob("*") if recursive else folder_path.glob("*")

    for p in iterator:
        if p.is_file():
            # Skip hidden files, system files, and manifest
            if p.name.startswith(".") or p.name == MANIFEST_FILENAME:
                continue
            if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(p)
    return files


def print_cluster_tree(result: TripClusterResult, folder_path: Path) -> None:
    """Print a rich visual journey tree of days, stops, and hero photos."""
    if not result.days:
        print(f"No trip days clustered for {folder_path}")
        return

    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.tree import Tree

        console = Console()
        summary = result.to_dict()["summary"]
        cov = summary["gps_coverage"]
        cov_str = (
            f"[green]{cov['recorded']}[/green] recorded, "
            f"[yellow]{cov['interpolated']}[/yellow] interpolated, "
            f"[red]{cov['none']}[/red] none"
        )

        root_label = (
            f"[bold cyan]Trip Journey ({folder_path.name})[/bold cyan]\n"
            f"  • Total: {summary['total_days']} Days, {summary['total_stops']} Stops, {summary['total_items']} Items\n"
            f"  • GPS Coverage: {cov_str}\n"
            f"  • Bursts: [magenta]{summary['burst_groups_count']} groups detected[/magenta]"
        )
        tree = Tree(root_label)

        for day in result.days:
            day_node = tree.add(
                f"[bold yellow]Day {day.day_number} ({day.date})[/bold yellow]: {len(day.stops)} Stops, {day.total_items} Items"
            )
            for stop in day.stops:
                loc_str = stop.location.get("city") or "Unknown"
                if stop.location.get("state") and stop.location["state"] != loc_str:
                    loc_str += f", {stop.location['state']}"
                if stop.location.get("country"):
                    loc_str += f", {stop.location['country']}"

                time_str = f"{stop.start_time.strftime('%I:%M %p').lstrip('0')} - {stop.end_time.strftime('%I:%M %p').lstrip('0')}"
                status_icon = "🏨" if stop.transit_status == "dwell" else "🚗"

                stop_label = f"[bold green]{stop.stop_id.upper()}: {stop.title}[/bold green]"
                stop_node = day_node.add(stop_label)
                stop_node.add(f"Timing: {time_str} ({stop.duration_minutes} min) | Status: {status_icon} [dim]{stop.transit_status}[/dim]")
                if stop.centroid_lat and stop.centroid_lon:
                    alt_str = f" | Elevation: {stop.avg_altitude}m" if stop.avg_altitude else ""
                    stop_node.add(f"Location: 📍 [cyan]{loc_str}[/cyan] ({stop.centroid_lat:.4f}, {stop.centroid_lon:.4f}{alt_str})")

                heroes = sum(1 for it in stop.items if it.metadata.get("is_hero_candidate"))
                hero_str = f" | [bold magenta]⭐ {heroes} Hero Candidates[/bold magenta]" if heroes > 0 else ""
                stop_node.add(f"Media: [bold]{len(stop.items)} items[/bold] ({stop.sun_phase.replace('_', ' ')}){hero_str}")

        console.print(Panel(tree, title="[bold]Spatiotemporal Trip Clustering (Phase 1)[/bold]"))
    except ImportError:
        # Fallback text
        print("=" * 70)
        print(f"Trip Journey: {len(result.days)} Days, {result.total_stops} Stops, {result.total_items} Items")
        print("=" * 70)
        for day in result.days:
            print(f"\nDay {day.day_number} ({day.date}) - {len(day.stops)} Stops:")
            for stop in day.stops:
                print(f"  [{stop.stop_id}] {stop.title} ({len(stop.items)} items)")
                if stop.centroid_lat:
                    print(f"    📍 {stop.location.get('formatted')} ({stop.centroid_lat:.4f}, {stop.centroid_lon:.4f})")


def main(argv: List[str] = None) -> int:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="chronocull",
        description="Extract embedded metadata, sort chronologically, cluster into travel stops, and rename trip media.",
    )
    parser.add_argument(
        "folder",
        type=str,
        help="Path to the directory containing trip media files.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute renaming operations on disk (default is safe dry-run preview).",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback previously renamed files in the directory using trip_manifest.json.",
    )
    parser.add_argument(
        "--cluster",
        action="store_true",
        help="Execute spatiotemporal clustering to organize media into Days, Stops, and Hero Candidates.",
    )
    parser.add_argument(
        "--export-story",
        action="store_true",
        help="Export trip_manifest_v2.json and trip_route.geojson for Phase 2 curation.",
    )
    parser.add_argument(
        "--export-social",
        action="store_true",
        help="Export zero-copy social staging packs (01_Carousel_Picks, 02_Stories_Vertical, captions.txt, story_overlays.txt).",
    )
    parser.add_argument(
        "--link-mode",
        choices=["auto", "hard", "symlink", "copy"],
        default="auto",
        help="File linking method for social export: 'auto' (hardlink -> symlink -> copy), 'hard', 'symlink', or 'copy' (default: auto).",
    )
    parser.add_argument(
        "--browser-assist",
        action="store_true",
        help="Launch browser-use staging assistant to inspect or draft Instagram upload using local browser profile.",
    )
    parser.add_argument(
        "--curate-ai",
        action="store_true",
        help="Run Multimodal AI Curation (Gemini) to score photos and generate TRAVELOGUE.md (requires GEMINI_API_KEY).",
    )
    parser.add_argument(
        "--enrich-apify",
        action="store_true",
        help="Run Apify POI web enrichment on stops before exporting (requires APIFY_TOKEN environment variable).",
    )
    parser.add_argument(
        "--online-geocode",
        action="store_true",
        help="Enable online Nominatim POI/landmark lookup with rate-limiting and local caching.",
    )
    parser.add_argument(
        "--no-heuristics",
        action="store_true",
        help="Skip perceptual hash and sharpness calculation during clustering.",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recursively scan subdirectories for media files.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default=None,
        help="Destination directory for exported media and story artifacts (default: output/<source_folder>).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Perform in-place renames inside source folder instead of exporting to output directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output plan or result as JSON to stdout.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args(argv)

    folder_path = Path(args.folder).resolve()
    if not folder_path.exists() or not folder_path.is_dir():
        print(f"Error: Directory '{folder_path}' does not exist or is not a directory.", file=sys.stderr)
        return 1
        
    # Load environment variables (.env in target folder or cwd/project root)
    if (folder_path / ".env").is_file():
        load_dotenv(folder_path / ".env")
    else:
        load_dotenv()

    if args.in_place:
        output_dir = folder_path
    else:
        output_dir = resolve_output_dir(folder_path, args.output_dir)

    # Handle Rollback
    if args.rollback:
        target_rollback = output_dir if (output_dir / MANIFEST_FILENAME).exists() else folder_path
        result = rollback_renames(target_rollback)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            status_icon = "✅" if result["success"] else "❌"
            print(f"{status_icon} {result['message']}")
        return 0 if result["success"] else 1

    # Scan media files
    media_files = scan_media_files(folder_path, recursive=args.recursive)
    if not media_files:
        if args.json:
            print(json.dumps({"error": "No supported media files found", "items": []}))
        else:
            print(f"No supported media files found in {folder_path}")
        return 0

    # Extract metadata for each item
    raw_items: List[MediaItem] = []
    for f in media_files:
        raw_items.append(extract_media_item(f))

    # Sort chronologically and plan names
    sorted_items = sort_and_plan_media(raw_items)

    apply_result = None
    if args.apply:
        try:
            apply_result = apply_renames(sorted_items, folder_path, output_dir=output_dir)
            if not args.json and not (args.cluster or args.export_story):
                print(f"\n✅ {apply_result['message']}")
                print(f"📄 Manifest written to: {apply_result['manifest_path']}\n")
        except Exception as e:
            if args.json:
                print(json.dumps({"success": False, "error": str(e)}))
            else:
                print(f"\n❌ Error applying renames: {e}", file=sys.stderr)
            return 1

    # Handle Clustering / Story Export / Social Export (Phase 1, 2 & 3)
    if args.cluster or args.export_story or args.export_social or args.browser_assist:
        cluster_res = cluster_trip_journey(
            sorted_items,
            allow_online_geocoding=args.online_geocode,
            run_heuristics=not args.no_heuristics,
        )

        if args.enrich_apify:
            if not args.json:
                print("\n🌐 Running Apify POI Enrichment...")
            run_enrichment_pipeline(cluster_res)

        if args.curate_ai:
            if not args.json:
                print("\n🧠 Running Multimodal AI Curation (Gemini)...")
            from chronocull.core.curation import curate_trip
            output_dir.mkdir(parents=True, exist_ok=True)
            curate_trip(cluster_res, output_dir, source_folder=folder_path)

        if args.export_story:
            from chronocull.core.html_showcase import generate_html_showcase
            output_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = write_story_manifest(output_dir, cluster_res)
            geojson_path = export_trip_geojson(output_dir, cluster_res)
            html_path = generate_html_showcase(cluster_res, output_dir)
            
            if not args.json:
                print(f"\n✅ Successfully exported Phase 1 & 2 Story Artifacts to {output_dir}:")
                print(f"  📄 Manifest V2: {manifest_path.name}")
                print(f"  🗺️  GeoJSON Route: {geojson_path.name}")
                print(f"  🖼️  HTML Album: {html_path.name}\n")

        social_stats = None
        if args.export_social or args.browser_assist:
            from chronocull.core.social import export_social_bundles
            social_dir = output_dir if output_dir != folder_path else folder_path / "Trip_Social_Ready"
            social_stats = export_social_bundles(
                cluster_res,
                social_dir,
                candidate_dirs=[folder_path, output_dir],
                link_mode=args.link_mode,
            )

            if not args.json:
                print(f"\n📸 Successfully exported Social Ready Packs to {social_dir}:")
                print(f"  🎡 Carousel Picks: {social_stats['total_carousel_picks']}")
                print(f"  📱 Vertical Stories: {social_stats['total_stories']}")
                print(f"  🎞️  B-Roll Extras: {social_stats['total_b_roll']}")
                print(f"  🗑️  Rejected Blurs/Bursts: {social_stats['total_rejected']}")
                print(f"  🔗 Link methods: {social_stats['link_methods_used']}\n")

        if args.browser_assist:
            from chronocull.core.browser_staging import run_browser_staging
            social_dir = output_dir if output_dir != folder_path else folder_path / "Trip_Social_Ready"
            staging_res = run_browser_staging(social_dir)
            if not args.json:
                print(f"\n🌐 Browser Staging: {staging_res['message']}\n")

        if args.json:
            result_dict = cluster_res.to_dict()
            if apply_result:
                result_dict["apply_result"] = apply_result
            result_dict["output_dir"] = str(output_dir)
            if social_stats:
                result_dict["social_export"] = social_stats
            print(json.dumps(result_dict, indent=2))
        else:
            if not args.export_story and not args.export_social and not args.browser_assist:
                print_cluster_tree(cluster_res, folder_path)

        return 0

    if args.apply:
        if args.json:
            print(json.dumps(apply_result, indent=2))
        return 0

    # Default: Dry-Run Preview
    if args.json:
        plan_data = {
            "folder": str(folder_path),
            "output_dir": str(output_dir),
            "total_items": len(sorted_items),
            "items": [item.to_dict() for item in sorted_items],
        }
        print(json.dumps(plan_data, indent=2))
    else:
        print_dry_run_table(sorted_items, output_dir=output_dir)

    return 0


if __name__ == "__main__":
    sys.exit(main())
