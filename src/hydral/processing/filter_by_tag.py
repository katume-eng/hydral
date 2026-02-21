from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


AUDIO_PATH_KEYS = (
    "audio_path",
    "wav",
    "source",
    "file",
    "filepath",
    "path",
    "audio",
    "audio_file",
    "audiofile",
)


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter JSON metadata by tag and copy matching audio files."
    )
    parser.add_argument("--data_dir", type=Path, default=Path("data"))
    parser.add_argument("--tag", type=str, default="low_freq_rich")
    parser.add_argument("--out_dir", type=Path, default=Path("data/selected/low_freq"))
    parser.add_argument("--ext", type=str, default="wav")
    parser.add_argument("--dry_run", action="store_true", help="Log only, no copy")
    parser.add_argument("--overwrite", action="store_true", help="Allow overwriting output")
    return parser.parse_args()


def normalize_ext(ext: str) -> str:
    return ext.lstrip(".").lower()


def iter_json_files(data_dir: Path) -> Iterable[Path]:
    return sorted(data_dir.rglob("*.json"))


def load_json(json_path: Path) -> Optional[Dict[str, Any]]:
    try:
        with json_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        log_warn(f"Invalid JSON skipped: {json_path} ({exc})")
        return None
    except OSError as exc:
        log_warn(f"Failed to read JSON skipped: {json_path} ({exc})")
        return None
    if not isinstance(data, dict):
        log_warn(f"JSON root is not an object, skipped: {json_path}")
        return None
    return data


def resolve_candidate_paths(
    value: str,
    *,
    json_dir: Path,
    data_dir: Path,
) -> List[Path]:
    raw_path = Path(value).expanduser()
    if raw_path.is_absolute():
        return [raw_path]
    return [json_dir / raw_path, data_dir / raw_path, raw_path]


def matches_ext(path: Path, *, ext: str) -> bool:
    return path.suffix.lower() == f".{ext}"


def find_audio_from_metadata(
    data: Dict[str, Any],
    *,
    json_path: Path,
    data_dir: Path,
    ext: str,
) -> Optional[Path]:
    json_dir = json_path.parent
    for key in AUDIO_PATH_KEYS:
        raw_value = data.get(key)
        if not isinstance(raw_value, str):
            continue
        for candidate in resolve_candidate_paths(raw_value, json_dir=json_dir, data_dir=data_dir):
            if candidate.exists() and candidate.is_file() and matches_ext(candidate, ext=ext):
                return candidate
    return None


def find_audio_by_basename(
    *,
    json_path: Path,
    data_dir: Path,
    ext: str,
) -> Tuple[Optional[Path], List[Path]]:
    basename = f"{json_path.stem}.{ext}"
    local_candidate = json_path.with_name(basename)
    if local_candidate.exists() and local_candidate.is_file():
        return local_candidate, []
    matches = [path for path in data_dir.rglob(basename) if path.is_file()]
    if not matches:
        return None, []
    if len(matches) == 1:
        return matches[0], matches
    matches_sorted = sorted(matches, key=lambda item: (len(str(item)), str(item)))
    return matches_sorted[0], matches_sorted


def choose_destination(
    *,
    out_dir: Path,
    src_path: Path,
    overwrite: bool,
) -> Path:
    destination = out_dir / src_path.name
    if overwrite or not destination.exists():
        return destination
    counter = 2
    while True:
        candidate = out_dir / f"{src_path.stem}__{counter}{src_path.suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def write_manifest(out_dir: Path, *, tag: str, items: List[Dict[str, Any]]) -> None:
    manifest = {
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "tag": tag,
        "items": items,
    }
    manifest_path = out_dir / "manifest.json"
    try:
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
    except OSError as exc:
        log_warn(f"Failed to write manifest: {manifest_path} ({exc})")


def main() -> None:
    args = parse_args()
    data_dir = args.data_dir
    out_dir = args.out_dir
    tag = args.tag
    ext = normalize_ext(args.ext)

    if not data_dir.exists() or not data_dir.is_dir():
        print(f"Error: data_dir not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    total_json = 0
    hit_count = 0
    copy_count = 0
    skip_reasons: Dict[str, int] = {}
    manifest_items: List[Dict[str, Any]] = []

    for json_path in iter_json_files(data_dir):
        total_json += 1
        data = load_json(json_path)
        if data is None:
            skip_reasons["invalid_json"] = skip_reasons.get("invalid_json", 0) + 1
            continue

        tags = data.get("tags")
        if not isinstance(tags, list):
            log_warn(f"Missing or invalid tags list, skipped: {json_path}")
            skip_reasons["invalid_tags"] = skip_reasons.get("invalid_tags", 0) + 1
            continue

        if tag not in tags:
            skip_reasons["tag_not_found"] = skip_reasons.get("tag_not_found", 0) + 1
            continue

        hit_count += 1
        wav_path = find_audio_from_metadata(
            data,
            json_path=json_path,
            data_dir=data_dir,
            ext=ext,
        )
        if wav_path is None:
            wav_path, matches = find_audio_by_basename(
                json_path=json_path,
                data_dir=data_dir,
                ext=ext,
            )
            if matches and len(matches) > 1:
                log_warn(
                    f"Multiple matches for {json_path.stem}.{ext}, using {wav_path}"
                )

        if wav_path is None:
            log_warn(f"Audio not found for JSON: {json_path}")
            skip_reasons["audio_not_found"] = skip_reasons.get("audio_not_found", 0) + 1
            continue

        destination = choose_destination(
            out_dir=out_dir,
            src_path=wav_path,
            overwrite=args.overwrite,
        )

        if args.dry_run:
            log_info(f"[DRY RUN] Would copy {wav_path} -> {destination}")
            continue

        try:
            shutil.copy2(wav_path, destination)
            log_info(f"Copied {wav_path} -> {destination}")
        except OSError as exc:
            log_warn(f"Copy failed: {wav_path} -> {destination} ({exc})")
            skip_reasons["copy_failed"] = skip_reasons.get("copy_failed", 0) + 1
            continue

        copy_count += 1
        manifest_items.append(
            {
                "json_path": str(json_path),
                "wav_src": str(wav_path),
                "wav_dst": str(destination),
                "tags": tags,
            }
        )

    if not args.dry_run:
        write_manifest(out_dir, tag=tag, items=manifest_items)

    skipped_total = sum(skip_reasons.values())
    log_info(f"Scanned JSON: {total_json}")
    log_info(f"Tag hits: {hit_count}")
    log_info(f"Copied: {copy_count}")
    log_info(f"Skipped: {skipped_total} ({skip_reasons})")


if __name__ == "__main__":
    main()

# Example:
#   python -m processing.filter_by_tag
#   python -m processing.filter_by_tag --tag high_freq_rich --out_dir data/selected/high_freq
#   python -m processing.filter_by_tag --dry_run
