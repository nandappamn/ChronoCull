"""Renamer module: handles dry-run previews, safe two-phase renames, and rollback operations."""

import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from chronocull.core.manifest import read_manifest, update_manifest_status, write_manifest
from chronocull.models import MediaItem

try:
    from rich.console import Console
    from rich.table import Table

    HAS_RICH = True
except ImportError:
    HAS_RICH = False


def print_dry_run_table(
    items: List[MediaItem], output_dir: Optional[Path] = None
) -> None:
    """Print a clean visual table of the proposed sorting and renaming plan."""
    if not items:
        print("No supported media files found in the specified directory.")
        return

    sources = Counter(item.timestamp_source for item in items)
    images_count = sum(1 for item in items if item.media_type == "image")
    videos_count = sum(1 for item in items if item.media_type == "video")
    warnings_count = sources.get("fs_fallback", 0)

    if HAS_RICH:
        console = Console()
        table = Table(title="[bold cyan]Trip Media Sorting & Renaming Plan (Dry-Run)[/bold cyan]")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Original Name", style="bold")
        table.add_column("Type", justify="center")
        table.add_column("Capture Timestamp", justify="center")
        table.add_column("Source", justify="center")
        table.add_column("Proposed New Name", style="green")

        for idx, item in enumerate(items, 1):
            ts_display = item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if item.subsecond:
                ts_display += f".{item.subsecond}"

            source_style = "green"
            if item.timestamp_source == "fs_fallback":
                source_style = "bold red"
            elif item.timestamp_source == "filename_regex":
                source_style = "yellow"

            type_display = "📷 Image" if item.media_type == "image" else "🎥 Video"
            source_display = f"[{source_style}]{item.timestamp_source}[/{source_style}]"

            table.add_row(
                str(idx),
                item.original_name,
                type_display,
                ts_display,
                source_display,
                item.proposed_name or "",
            )

        console.print(table)
        console.print("\n[bold]Summary:[/bold]")
        console.print(f"  • Total media items: [cyan]{len(items)}[/cyan] ({images_count} images, {videos_count} videos)")
        for src, count in sources.items():
            color = "red" if src == "fs_fallback" else "green"
            console.print(f"  • [{color}]{src}[/{color}]: {count}")
        if warnings_count > 0:
            console.print(f"  • [bold red]⚠️  {warnings_count} files lacked embedded metadata and fell back to filesystem timestamps.[/bold red]")

        if output_dir:
            console.print(f"\n[bold]Export Target Directory:[/bold] [cyan]{output_dir}[/cyan]")
        console.print("\n[bold yellow]🔍 DRY-RUN MODE ACTIVE:[/bold yellow] No files were modified on disk.")
        console.print("To execute these renames, re-run with: [bold green]--apply[/bold green]\n")
    else:
        # Fallback ASCII table
        print("=" * 80)
        print(f"{'#':<4} {'Type':<7} {'Original Name':<30} {'Timestamp':<20} {'Source':<15}")
        print("=" * 80)
        for idx, item in enumerate(items, 1):
            ts_display = item.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            print(f"{idx:<4} {item.media_type:<7} {item.original_name[:28]:<30} {ts_display:<20} {item.timestamp_source:<15}")
            print(f"     ➔ {item.proposed_name}")
        print("=" * 80)
        print(f"Total: {len(items)} items ({images_count} images, {videos_count} videos)")
        print(f"Sources: {dict(sources)}")
        if warnings_count > 0:
            print(f"WARNING: {warnings_count} files fell back to filesystem timestamp.")
        if output_dir:
            print(f"\nExport Target Directory: {output_dir}")
        print("\nDRY-RUN MODE ACTIVE: No files modified. Re-run with --apply to rename.")


def apply_renames(
    items: List[MediaItem],
    folder_path: Path,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute renaming operations.
    
    If output_dir is specified and distinct from folder_path, exports/copies files to output_dir
    with proposed names, leaving original source media files completely untouched.
    Otherwise, executes safe in-place two-phase atomic renames within folder_path.
    """
    if not items:
        return {"success": True, "renamed": 0, "message": "No media items to rename."}

    # Verify all files exist
    for item in items:
        if not item.original_path.exists():
            raise FileNotFoundError(f"File not found during pre-flight check: {item.original_path}")

    # Export mode: Copy to output_dir leaving original folder_path files untouched
    if output_dir is not None and output_dir.resolve() != folder_path.resolve():
        output_dir.mkdir(parents=True, exist_ok=True)
        copied_count = 0
        for item in items:
            proposed = item.proposed_name or item.original_name
            try:
                rel_parent = item.original_path.resolve().relative_to(folder_path.resolve()).parent
            except ValueError:
                rel_parent = Path(".")

            dest_dir = output_dir / rel_parent
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / proposed

            shutil.copy2(item.original_path, dest_path)
            item.target_path = dest_path
            copied_count += 1

        manifest_path = write_manifest(output_dir, items, status="exported", source_folder=folder_path)
        return {
            "success": True,
            "renamed": copied_count,
            "manifest_path": str(manifest_path),
            "output_dir": str(output_dir),
            "mode": "export",
            "message": f"Successfully exported {copied_count} renamed files to {output_dir} (source untouched)",
        }

    # In-place mode: Two-phase rename staging within folder_path
    temp_moves: List[Tuple[Path, Path, MediaItem]] = []
    renamed_count = 0

    try:
        for item in items:
            if not item.proposed_name or not item.target_path:
                continue

            # If already named as proposed, skip disk move
            if item.original_name == item.proposed_name:
                continue

            temp_path = item.original_path.with_name(f".tmp_{uuid.uuid4().hex}_{item.original_name}")
            item.original_path.rename(temp_path)
            temp_moves.append((temp_path, item.target_path, item))

        # Phase 2: Rename from temp staging to final proposed target
        final_moves: List[Tuple[Path, Path]] = []
        for temp_path, final_target, item in temp_moves:
            temp_path.rename(final_target)
            final_moves.append((temp_path, final_target))
            renamed_count += 1

        # Write manifest
        manifest_path = write_manifest(folder_path, items, status="applied")

        return {
            "success": True,
            "renamed": renamed_count,
            "manifest_path": str(manifest_path),
            "output_dir": str(folder_path),
            "mode": "in_place",
            "message": f"Successfully renamed {renamed_count} files and generated {manifest_path.name}",
        }

    except Exception as e:
        # Rollback partial moves if failure occurs during phase 2
        for temp_path, final_target in reversed(final_moves):
            try:
                if final_target.exists():
                    final_target.rename(temp_path)
            except Exception:
                pass
        for temp_path, _, item in reversed(temp_moves):
            try:
                if temp_path.exists():
                    temp_path.rename(item.original_path)
            except Exception:
                pass
        raise RuntimeError(f"Error during renaming operation, reverted staged changes: {e}") from e


def rollback_renames(folder_path: Path) -> Dict[str, Any]:
    """Revert files to their original state using trip_manifest.json.
    
    If the manifest represents an export (status == 'exported'), removes the exported
    files in folder_path. Otherwise, reverts in-place renamed files back to their original names.
    """
    manifest = read_manifest(folder_path)
    if not manifest:
        return {
            "success": False,
            "reverted": 0,
            "message": f"No trip_manifest.json found in {folder_path}. Cannot rollback.",
        }

    if manifest.get("status") == "rolled_back":
        return {
            "success": False,
            "reverted": 0,
            "message": "Manifest is already marked as 'rolled_back'.",
        }

    is_exported_mode = manifest.get("status") == "exported" or (
        bool(manifest.get("source_folder"))
        and manifest.get("source_folder") != manifest.get("folder_path")
    )
    items_data = manifest.get("items", [])
    reverted_count = 0
    missing_files: List[str] = []

    if is_exported_mode:
        for entry in items_data:
            rel_target = entry.get("rel_target_path") or entry.get("renamed_to")
            if not rel_target:
                continue
            target_file = folder_path / rel_target
            if target_file.exists():
                try:
                    target_file.unlink()
                    reverted_count += 1
                except Exception as e:
                    missing_files.append(f"{rel_target}: {e}")
            else:
                missing_files.append(rel_target)

        update_manifest_status(folder_path, "rolled_back")
        msg = f"Successfully rolled back export: removed {reverted_count} exported files from {folder_path}."
        if missing_files:
            msg += f" ({len(missing_files)} files could not be removed)"

        return {
            "success": True,
            "reverted": reverted_count,
            "missing": missing_files,
            "message": msg,
        }

    # In-place mode rollback
    for entry in items_data:
        orig_name = entry.get("original_name")
        renamed_to = entry.get("renamed_to")

        if not orig_name or not renamed_to or orig_name == renamed_to:
            continue

        rel_target = entry.get("rel_target_path") or entry.get("renamed_to")
        rel_orig = entry.get("rel_original_path") or entry.get("original_name")

        current_file = folder_path / rel_target
        original_file = folder_path / rel_orig

        if not current_file.exists():
            missing_files.append(rel_target)
            continue

        current_file.rename(original_file)
        reverted_count += 1

    update_manifest_status(folder_path, "rolled_back")

    msg = f"Successfully rolled back {reverted_count} files to original names."
    if missing_files:
        msg += f" (Note: {len(missing_files)} renamed files could not be found: {missing_files[:3]})"

    return {
        "success": True,
        "reverted": reverted_count,
        "missing": missing_files,
        "message": msg,
    }
