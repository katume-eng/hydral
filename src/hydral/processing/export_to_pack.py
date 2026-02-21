from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def log_error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Hydral pipeline outputs to sales material packs."
    )
    parser.add_argument(
        "--src",
        type=Path,
        required=True,
        help="Source directory containing generated files (required)",
    )
    parser.add_argument(
        "--dst",
        type=Path,
        required=True,
        help="Destination pack directory (e.g., data/packs/v1/water_sfx) (required)",
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["copy", "hardlink", "symlink"],
        default="copy",
        help="Export method (default: copy)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="*.*",
        help="Glob pattern for source files (default: *.*)",
    )
    parser.add_argument(
        "--group-by-stem",
        action="store_true",
        default=True,
        help="Group files by stem/basename (default: True)",
    )
    parser.add_argument(
        "--no-group-by-stem",
        dest="group_by_stem",
        action="store_false",
        help="Disable grouping by stem",
    )
    parser.add_argument(
        "--include-ext",
        type=str,
        default="",
        help="Comma-separated whitelist of extensions (e.g., wav,json,png)",
    )
    parser.add_argument(
        "--exclude-ext",
        type=str,
        default="",
        help="Comma-separated blacklist of extensions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned operations without making changes",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in destination",
    )
    parser.add_argument(
        "--rename-prefix",
        type=str,
        default="",
        help="Prefix to add to destination filenames",
    )
    parser.add_argument(
        "--rename-suffix",
        type=str,
        default="",
        help="Suffix to add to destination filenames (before extension)",
    )
    parser.add_argument(
        "--pack-manifest",
        action="store_true",
        default=True,
        help="Generate/update manifest.json (default: True)",
    )
    parser.add_argument(
        "--no-pack-manifest",
        dest="pack_manifest",
        action="store_false",
        help="Do not generate manifest.json",
    )
    parser.add_argument(
        "--manifest-name",
        type=str,
        default="manifest.json",
        help="Name of manifest file (default: manifest.json)",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Place all files directly in dst without type subdirectories",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on symlink/hardlink errors instead of falling back to copy",
    )
    return parser.parse_args()


# Extension to type mapping
EXT_TO_TYPE = {
    "wav": "audio",
    "mp3": "audio",
    "flac": "audio",
    "ogg": "audio",
    "m4a": "audio",
    "png": "images",
    "jpg": "images",
    "jpeg": "images",
    "webp": "images",
    "gif": "images",
    "mid": "midi",
    "midi": "midi",
    "json": "meta",
    "txt": "meta",
    "yaml": "meta",
    "yml": "meta",
}


def normalize_ext(ext: str) -> str:
    """Normalize extension by removing leading dot and converting to lowercase."""
    return ext.lstrip(".").lower()


def get_file_type(path: Path) -> str:
    """Determine file type category from extension."""
    ext = normalize_ext(path.suffix)
    return EXT_TO_TYPE.get(ext, "other")


def parse_ext_list(ext_str: str) -> Set[str]:
    """Parse comma-separated extension list into normalized set."""
    if not ext_str:
        return set()
    return {normalize_ext(e.strip()) for e in ext_str.split(",") if e.strip()}


def should_include_file(path: Path, include_exts: Set[str], exclude_exts: Set[str]) -> bool:
    """Check if file should be included based on extension filters."""
    ext = normalize_ext(path.suffix)
    if exclude_exts and ext in exclude_exts:
        return False
    if include_exts and ext not in include_exts:
        return False
    return True


def scan_files(
    src_dir: Path,
    pattern: str,
    include_exts: Set[str],
    exclude_exts: Set[str],
) -> List[Path]:
    """Scan source directory for matching files."""
    if not src_dir.exists():
        log_error(f"Source directory does not exist: {src_dir}")
        sys.exit(1)
    
    if not src_dir.is_dir():
        log_error(f"Source path is not a directory: {src_dir}")
        sys.exit(1)
    
    files = []
    for path in src_dir.rglob(pattern):
        if path.is_file() and should_include_file(path, include_exts, exclude_exts):
            files.append(path)
    
    return sorted(files)


def group_files_by_stem(files: List[Path]) -> Dict[str, List[Path]]:
    """Group files by their stem (basename without extension)."""
    groups: Dict[str, List[Path]] = defaultdict(list)
    for path in files:
        groups[path.stem].append(path)
    return dict(groups)


def compute_sha256(path: Path) -> Optional[str]:
    """Compute SHA256 hash of a file."""
    try:
        sha256_hash = hashlib.sha256()
        with path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except OSError as exc:
        log_warn(f"Failed to compute hash for {path}: {exc}")
        return None


def get_file_size(path: Path) -> int:
    """Get file size in bytes."""
    try:
        return path.stat().st_size
    except OSError:
        return 0


def load_json_metadata(path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON metadata file."""
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log_warn(f"Failed to load JSON metadata from {path}: {exc}")
        return None


def extract_pack_version(dst_path: Path) -> str:
    """Extract pack version from destination path (e.g., v1, v2)."""
    parts = dst_path.parts
    for part in parts:
        if part.startswith("v") and part[1:].isdigit():
            return part
    return "v1"


def apply_rename(filename: str, prefix: str, suffix: str) -> str:
    """Apply prefix and suffix to filename."""
    stem = Path(filename).stem
    ext = Path(filename).suffix
    return f"{prefix}{stem}{suffix}{ext}"


def perform_export(
    src_path: Path,
    dst_path: Path,
    mode: str,
    strict: bool,
) -> bool:
    """Perform the actual file export operation."""
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        
        if mode == "copy":
            shutil.copy2(src_path, dst_path)
        elif mode == "hardlink":
            try:
                os.link(src_path, dst_path)
            except OSError as exc:
                if strict:
                    raise
                log_warn(f"Hardlink failed, falling back to copy: {exc}")
                shutil.copy2(src_path, dst_path)
        elif mode == "symlink":
            try:
                # Use absolute path for symlink source to avoid issues
                dst_path.symlink_to(src_path.resolve())
            except OSError as exc:
                if strict:
                    raise
                log_warn(f"Symlink failed, falling back to copy: {exc}")
                shutil.copy2(src_path, dst_path)
        return True
    except OSError as exc:
        log_error(f"Export failed for {src_path} -> {dst_path}: {exc}")
        return False


def plan_export_operations(
    files: List[Path],
    src_dir: Path,
    dst_dir: Path,
    flat: bool,
    prefix: str,
    suffix: str,
    overwrite: bool,
) -> List[Tuple[Path, Path, str]]:
    """Plan all export operations, returning list of (src, dst, file_type) tuples."""
    operations = []
    conflicts = []
    
    for src_path in files:
        file_type = get_file_type(src_path)
        
        # Determine destination subdirectory
        if flat:
            subdir = dst_dir
        else:
            subdir = dst_dir / file_type
        
        # Apply renaming
        new_filename = apply_rename(src_path.name, prefix, suffix)
        dst_path = subdir / new_filename
        
        # Check for conflicts
        if dst_path.exists() and not overwrite:
            conflicts.append((src_path, dst_path))
        else:
            operations.append((src_path, dst_path, file_type))
    
    if conflicts:
        log_warn(f"Found {len(conflicts)} file conflicts (use --overwrite to replace):")
        for src, dst in conflicts[:5]:  # Show first 5
            log_warn(f"  {dst.name} already exists")
        if len(conflicts) > 5:
            log_warn(f"  ... and {len(conflicts) - 5} more")
    
    return operations


def build_manifest_items(
    operations: List[Tuple[Path, Path, str]],
    src_dir: Path,
    dst_dir: Path,
    group_by_stem: bool,
    use_dst_paths: bool = True,
) -> List[Dict[str, Any]]:
    """Build manifest items from export operations."""
    if group_by_stem:
        # Group by stem - keep track of both src and dst paths
        stem_groups: Dict[str, Dict[str, List[Tuple[Path, Path]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        
        for src_path, dst_path, file_type in operations:
            stem = dst_path.stem
            stem_groups[stem][file_type].append((src_path, dst_path))
        
        items = []
        for stem, type_files in sorted(stem_groups.items()):
            # Find metadata for tags - use source if dst doesn't exist yet
            tags = []
            for src_path, dst_path in type_files.get("meta", []):
                if src_path.suffix.lower() == ".json":
                    check_path = dst_path if use_dst_paths and dst_path.exists() else src_path
                    metadata = load_json_metadata(check_path)
                    if metadata and "tags" in metadata:
                        tags = metadata.get("tags", [])
                        break
            
            # Calculate hash for audio files - use source if dst doesn't exist yet
            audio_hash = None
            total_size = 0
            for src_path, dst_path in type_files.get("audio", []):
                check_path = dst_path if use_dst_paths and dst_path.exists() else src_path
                if audio_hash is None:  # Only hash first audio file
                    audio_hash = compute_sha256(check_path)
                total_size += get_file_size(check_path)
            
            # Add sizes for other files
            for file_type in ["images", "midi", "meta"]:
                for src_path, dst_path in type_files.get(file_type, []):
                    check_path = dst_path if use_dst_paths and dst_path.exists() else src_path
                    total_size += get_file_size(check_path)
            
            # Build relative paths
            files_dict = {}
            for file_type, path_pairs in type_files.items():
                rel_paths = [str(dst_path.relative_to(dst_dir)) for _, dst_path in path_pairs]
                files_dict[file_type] = sorted(rel_paths)
            
            item = {
                "id": stem,
                "files": files_dict,
            }
            if audio_hash:
                item["sha256"] = audio_hash
            if total_size > 0:
                item["size_bytes"] = total_size
            if tags:
                item["tags"] = tags
            
            items.append(item)
    else:
        # Simple file list
        items = []
        for src_path, dst_path, file_type in operations:
            rel_path = str(dst_path.relative_to(dst_dir))
            item = {
                "id": dst_path.stem,
                "file": rel_path,
                "type": file_type,
                "size_bytes": get_file_size(src_path),
            }
            items.append(item)
    
    return items


def load_existing_manifest(manifest_path: Path) -> Dict[str, Any]:
    """Load existing manifest or return empty template."""
    if manifest_path.exists():
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log_warn(f"Failed to load existing manifest, creating new: {exc}")
    
    return {
        "pack_version": "",
        "generated_at": "",
        "source_dir": "",
        "export_mode": "",
        "items": [],
    }


def update_manifest(
    manifest_path: Path,
    src_dir: Path,
    dst_dir: Path,
    mode: str,
    new_items: List[Dict[str, Any]],
) -> None:
    """Update or create manifest.json."""
    manifest = load_existing_manifest(manifest_path)
    
    # Update metadata
    manifest["pack_version"] = extract_pack_version(dst_dir)
    manifest["generated_at"] = datetime.now(timezone.utc).isoformat()
    manifest["source_dir"] = str(src_dir)
    manifest["export_mode"] = mode
    
    # Merge items (update existing by id, add new)
    existing_items = {item["id"]: item for item in manifest.get("items", [])}
    for new_item in new_items:
        existing_items[new_item["id"]] = new_item
    
    manifest["items"] = sorted(existing_items.values(), key=lambda x: x["id"])
    
    # Write manifest
    try:
        with manifest_path.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        log_info(f"Manifest updated: {manifest_path}")
    except OSError as exc:
        log_error(f"Failed to write manifest: {exc}")


def main() -> None:
    args = parse_args()
    
    # Parse extension filters
    include_exts = parse_ext_list(args.include_ext)
    exclude_exts = parse_ext_list(args.exclude_ext)
    
    # Scan source files
    log_info(f"Scanning source: {args.src}")
    files = scan_files(args.src, args.pattern, include_exts, exclude_exts)
    
    if not files:
        log_error(f"No files found matching criteria in {args.src}")
        sys.exit(1)
    
    log_info(f"Found {len(files)} files")
    
    # Plan export operations
    operations = plan_export_operations(
        files,
        args.src,
        args.dst,
        args.flat,
        args.rename_prefix,
        args.rename_suffix,
        args.overwrite,
    )
    
    if not operations:
        log_warn("No files to export after conflict resolution")
        sys.exit(0)
    
    # Dry run mode
    if args.dry_run:
        log_info(f"[DRY RUN] Would export {len(operations)} files:")
        for src, dst, file_type in operations[:10]:  # Show first 10
            log_info(f"  [{args.mode}] {src.name} -> {dst.relative_to(args.dst)}")
        if len(operations) > 10:
            log_info(f"  ... and {len(operations) - 10} more")
        
        # Show manifest preview
        if args.pack_manifest:
            manifest_items = build_manifest_items(
                operations, args.src, args.dst, args.group_by_stem, use_dst_paths=False
            )
            log_info(f"[DRY RUN] Would create/update manifest with {len(manifest_items)} items")
        
        sys.exit(0)
    
    # Perform actual export
    log_info(f"Exporting {len(operations)} files to {args.dst}")
    success_count = 0
    failed_count = 0
    
    for src_path, dst_path, file_type in operations:
        if perform_export(src_path, dst_path, args.mode, args.strict):
            success_count += 1
            log_info(f"Exported: {src_path.name} -> {dst_path.relative_to(args.dst)}")
        else:
            failed_count += 1
    
    # Update manifest
    if args.pack_manifest and success_count > 0:
        manifest_path = args.dst / args.manifest_name
        manifest_items = build_manifest_items(
            operations, args.src, args.dst, args.group_by_stem, use_dst_paths=True
        )
        update_manifest(manifest_path, args.src, args.dst, args.mode, manifest_items)
    
    # Summary
    log_info("=" * 60)
    log_info(f"Export complete:")
    log_info(f"  Total planned: {len(operations)}")
    log_info(f"  Successfully exported: {success_count}")
    log_info(f"  Failed: {failed_count}")
    log_info(f"  Skipped (conflicts): {len(files) - len(operations)}")
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()


# Example usage:
#   python processing/export_to_pack.py --src data/processed/run_20260215 --dst data/packs/v1/water_sfx --mode copy --include-ext wav,json,png --overwrite
#   python processing/export_to_pack.py --src data/generated/songmaking/out --dst data/packs/v1/midi_pack --mode hardlink --include-ext mid,json --dry-run
#   python -m processing.export_to_pack --src data/test --dst data/packs/v1/test --dry-run
