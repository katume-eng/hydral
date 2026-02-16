from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import librosa
import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from analysis.audio_features.io import load_audio_waveform

MIN_FREQ_HZ = 20.0
LOW_FREQ_MAX_HZ = 200.0


def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}", file=sys.stderr)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="低周波リッチな音源に low_freq_rich タグを付与する。"
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--ext", type=str, default="wav")
    parser.add_argument("--threshold", type=float, default=0.25)
    parser.add_argument("--dry-run", action="store_true", help="変更内容のみ表示")
    parser.add_argument("--backup", action="store_true", help=".bak を作成")
    parser.add_argument(
        "--remove-if-not-rich",
        action="store_true",
        help="低域が不足する場合に low_freq_rich を削除",
    )
    parser.add_argument("--hop-length", type=int, default=512)
    return parser.parse_args()


def normalize_ext(ext: str) -> str:
    return ext.lstrip(".").lower()


def iter_audio_files(data_root: Path, *, ext: str) -> List[Path]:
    return sorted(path for path in data_root.rglob(f"*.{ext}") if path.is_file())


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


def compute_low_band_ratio(
    wav_path: Path,
    *,
    hop_length: int,
) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    try:
        waveform, sample_rate = load_audio_waveform(wav_path, target_sample_rate=None)
        if waveform.size == 0:
            return None, "empty_waveform", None

        stft_complex = librosa.stft(waveform, hop_length=hop_length)
        if stft_complex.size == 0:
            return None, "empty_stft", None

        power_spectrogram = np.abs(stft_complex) ** 2
        frequency_bins_hz = librosa.fft_frequencies(sr=sample_rate)

        valid_mask = frequency_bins_hz >= MIN_FREQ_HZ
        if not np.any(valid_mask):
            return None, "invalid_frequency_range", None

        total_energy = float(power_spectrogram[valid_mask].sum())
        if total_energy <= 0.0 or not math.isfinite(total_energy):
            return None, "silent_audio", None

        low_mask = (frequency_bins_hz >= MIN_FREQ_HZ) & (
            frequency_bins_hz < LOW_FREQ_MAX_HZ
        )
        if not np.any(low_mask):
            return None, "low_band_missing", None

        low_energy = float(power_spectrogram[low_mask].sum())
        ratio = low_energy / total_energy
        if not math.isfinite(ratio):
            return None, "ratio_invalid", None

        return ratio, None, None
    except OSError as exc:
        return None, "load_failed", str(exc)
    except Exception as exc:
        return None, "analysis_failed", str(exc)


def write_json(
    json_path: Path,
    *,
    data: Dict[str, Any],
    backup: bool,
) -> None:
    if backup:
        backup_path = json_path.with_suffix(json_path.suffix + ".bak")
        shutil.copy2(json_path, backup_path)

    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    data_root = args.data_root
    ext = normalize_ext(args.ext)

    if not data_root.exists() or not data_root.is_dir():
        print(f"Error: data-root not found: {data_root}", file=sys.stderr)
        sys.exit(1)

    wav_paths = iter_audio_files(data_root, ext=ext)
    total_wav = len(wav_paths)

    analyzed_count = 0
    updated_count = 0
    added_count = 0
    removed_count = 0
    skip_reasons: Dict[str, int] = {}

    for index, wav_path in enumerate(wav_paths, start=1):
        log_info(f"[{index}/{total_wav}] {wav_path}")
        json_path = wav_path.with_suffix(".json")
        if not json_path.exists():
            log_warn(f"JSON not found, skipped: {json_path}")
            skip_reasons["missing_json"] = skip_reasons.get("missing_json", 0) + 1
            continue

        data = load_json(json_path)
        if data is None:
            skip_reasons["invalid_json"] = skip_reasons.get("invalid_json", 0) + 1
            continue

        ratio, error_reason, error_detail = compute_low_band_ratio(
            wav_path,
            hop_length=args.hop_length,
        )
        if ratio is None:
            detail = f": {error_detail}" if error_detail else ""
            log_warn(f"Analysis skipped: {wav_path} ({error_reason}{detail})")
            reason_key = error_reason or "analysis_failed"
            skip_reasons[reason_key] = (
                skip_reasons.get(reason_key, 0) + 1
            )
            continue

        analyzed_count += 1

        tags = data.get("tags")
        tags_created = False
        if tags is None:
            tags = []
            data["tags"] = tags
            tags_created = True
        if not isinstance(tags, list):
            log_warn(f"Invalid tags list, skipped: {json_path}")
            skip_reasons["invalid_tags"] = skip_reasons.get("invalid_tags", 0) + 1
            continue

        existing_ratio = data.get("low_band_ratio")
        ratio_changed = True
        if isinstance(existing_ratio, (int, float)) and math.isfinite(existing_ratio):
            ratio_changed = abs(existing_ratio - ratio) > 1e-9
        data["low_band_ratio"] = ratio

        is_rich = ratio >= args.threshold
        tags_changed = tags_created

        if is_rich:
            if "low_freq_rich" not in tags:
                tags.append("low_freq_rich")
                added_count += 1
                tags_changed = True
        elif args.remove_if_not_rich:
            removed = 0
            while "low_freq_rich" in tags:
                tags.remove("low_freq_rich")
                removed += 1
            if removed:
                removed_count += removed
                tags_changed = True

        if not (tags_changed or ratio_changed):
            continue

        updated_count += 1
        if args.dry_run:
            log_info(
                f"[DRY RUN] {json_path}: low_band_ratio={ratio:.4f}, "
                f"rich={is_rich}, tags={tags}"
            )
            continue

        try:
            write_json(json_path, data=data, backup=args.backup)
            log_info(f"Updated: {json_path} (low_band_ratio={ratio:.4f})")
        except OSError as exc:
            log_warn(f"Failed to write JSON: {json_path} ({exc})")
            skip_reasons["write_failed"] = skip_reasons.get("write_failed", 0) + 1

    skipped_total = sum(skip_reasons.values())
    log_info(f"Scanned WAV: {total_wav}")
    log_info(f"Analyzed: {analyzed_count}")
    log_info(f"Updated JSON: {updated_count}")
    log_info(f"Tag added: {added_count}")
    log_info(f"Tag removed: {removed_count}")
    log_info(f"Skipped: {skipped_total} ({skip_reasons})")


if __name__ == "__main__":
    main()
