"""
Generate a short low-frequency loop from extracted audio materials.

Usage:
    python -m songMaking.lowfrec_track --input_dir path/to/lowfrec_samples
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from pydub import AudioSegment

from infra.audio import load_wav, export_wav
from processing.assemble import safe_normalize
from processing.loop import loop_grains
from processing.slice import slice_grains
from processing.transform_mics import shuffle


def find_wav_files(input_dir: Path) -> List[Path]:
    return sorted(p for p in input_dir.glob("*.wav") if p.is_file())


def build_lowfrec_loop(
    wav_paths: List[Path],
    *,
    grain_ms: int,
    duration_ms: int,
    crossfade_ms: int,
    seed: int | None = None,
) -> AudioSegment:
    grains: List[AudioSegment] = []
    for wav_path in wav_paths:
        audio = load_wav(wav_path)
        grains.extend(
            slice_grains(
                audio,
                grain_ms=grain_ms,
                hop_ms=grain_ms,
                jitter_ms=0,
                pad_end=False,
                fade_ms=max(0, crossfade_ms // 2),
                seed=seed,
            )
        )

    if not grains:
        return AudioSegment.silent(duration=0)

    grains = shuffle(grains, seed=seed)
    looped = loop_grains(grains, duration_ms=duration_ms, crossfade_ms=crossfade_ms)
    return safe_normalize(looped)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a short low-frequency loop from extracted audio materials"
    )
    parser.add_argument(
        "--input_dir",
        required=True,
        type=Path,
        help="Directory containing low-frequency extracted WAV files",
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("songMaking/output/lowfrec"),
        help="Output directory for generated loop (default: songMaking/output/lowfrec)",
    )
    parser.add_argument(
        "--duration_sec",
        type=float,
        default=8.0,
        help="Target loop duration in seconds (default: 8.0)",
    )
    parser.add_argument(
        "--grain_ms",
        type=int,
        default=320,
        help="Grain length in milliseconds (default: 320)",
    )
    parser.add_argument(
        "--crossfade_ms",
        type=int,
        default=12,
        help="Crossfade length between grains in milliseconds (default: 12)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for grain shuffling",
    )

    args = parser.parse_args()

    input_dir = args.input_dir
    if not input_dir.exists():
        print(f"Error: input_dir not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    wav_paths = find_wav_files(input_dir)
    if not wav_paths:
        print(f"Error: no WAV files found in {input_dir}", file=sys.stderr)
        sys.exit(1)

    duration_ms = max(0, int(args.duration_sec * 1000))
    if duration_ms == 0:
        print("Error: duration_sec must be positive", file=sys.stderr)
        sys.exit(1)

    if args.seed is None:
        seed = random.randint(0, 1_000_000)
    else:
        seed = args.seed

    loop_audio = build_lowfrec_loop(
        wav_paths,
        grain_ms=max(1, args.grain_ms),
        duration_ms=duration_ms,
        crossfade_ms=max(0, args.crossfade_ms),
        seed=seed,
    )

    if len(loop_audio) <= 0:
        print("Error: failed to build loop audio from provided samples", file=sys.stderr)
        sys.exit(1)

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"lowfrec_loop_{timestamp}.wav"

    export_wav(loop_audio, output_path)
    print(f"Generated loop: {output_path}")
    print(f"Duration: {len(loop_audio) / 1000:.2f}s, Seed: {seed}")


if __name__ == "__main__":
    main()
