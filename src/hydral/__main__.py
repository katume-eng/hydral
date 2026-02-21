"""python -m hydral  –  minimal pipeline runner for hydral.

Commands
--------
analyze
    Extract audio features (RMS, bands, onset) to JSON files under
    data/processed/hydral/<stem>/.

process
    Apply one or more audio transformations (normalize, band-split, grain)
    and write the results to data/processed/hydral/<stem>/.

Examples
--------
Analyze every WAV in data/raw/::

    python -m hydral analyze data/raw/

Normalize + band-split a single file::

    python -m hydral process data/raw/track.wav --normalize --band-split

Granular shuffle with a custom output directory::

    python -m hydral process data/raw/track.wav --grain --out /tmp/out
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SUPPORTED_EXTS = {".wav", ".mp3", ".flac"}


# ── helpers ─────────────────────────────────────────────────────────────────

def _collect_inputs(src: Path) -> list[Path]:
    """Return a sorted list of audio files from *src* (file or folder)."""
    if src.is_file():
        if src.suffix.lower() not in _SUPPORTED_EXTS:
            sys.exit(f"Unsupported file type: {src.suffix!r}")
        return [src]
    if src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in _SUPPORTED_EXTS)
        if not files:
            sys.exit(f"No audio files found in {src}")
        return files
    sys.exit(f"Input path not found: {src}")


# ── sub-command handlers ─────────────────────────────────────────────────────

def _cmd_analyze(args: argparse.Namespace) -> None:
    from hydral.pipeline import Pipeline, PipelineContext
    from hydral.steps import AnalyzeStep

    inputs = _collect_inputs(args.input)
    pipeline = Pipeline([
        AnalyzeStep(hop_length=args.hop_length, smoothing_window=args.smoothing_window),
    ])

    for wav in inputs:
        print(f"Analyzing {wav.name} …")
        ctx = PipelineContext(
            input_path=wav,
            output_dir=args.out / wav.stem,
            sample_rate=args.sr,
        )
        pipeline.run(ctx)


def _cmd_process(args: argparse.Namespace) -> None:
    from hydral.pipeline import Pipeline, PipelineContext
    from hydral.steps import BandSplitStep, GrainStep, NormalizeStep

    steps = []
    if args.normalize:
        steps.append(NormalizeStep())
    if args.band_split:
        steps.append(BandSplitStep())
    if args.grain:
        steps.append(GrainStep(grain_sec=args.grain_sec, seed=args.seed))

    if not steps:
        sys.exit(
            "No processing steps selected. "
            "Use --normalize, --band-split, and/or --grain."
        )

    inputs = _collect_inputs(args.input)
    pipeline = Pipeline(steps)

    for wav in inputs:
        print(f"Processing {wav.name} …")
        ctx = PipelineContext(
            input_path=wav,
            output_dir=args.out / wav.stem,
        )
        pipeline.run(ctx)


# ── argument parser ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hydral",
        description="Hydral audio pipeline runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── analyze ──────────────────────────────────────────────────────────────
    p_an = sub.add_parser("analyze", help="Extract audio features to JSON")
    p_an.add_argument("input", type=Path, help="Input WAV/MP3/FLAC file or folder")
    p_an.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/hydral"),
        metavar="DIR",
        help="Root output directory (default: data/processed/hydral)",
    )
    p_an.add_argument(
        "--sr",
        type=int,
        default=None,
        metavar="HZ",
        help="Resample to this sample rate before analysis (default: keep original)",
    )
    p_an.add_argument(
        "--hop-length",
        type=int,
        default=512,
        metavar="N",
        help="Analysis frame hop in samples (default: 512)",
    )
    p_an.add_argument(
        "--smoothing-window",
        type=int,
        default=5,
        metavar="N",
        help="Moving-average window size for smoothing (default: 5)",
    )

    # ── process ──────────────────────────────────────────────────────────────
    p_pr = sub.add_parser("process", help="Apply audio transformations")
    p_pr.add_argument("input", type=Path, help="Input WAV/MP3/FLAC file or folder")
    p_pr.add_argument(
        "--out",
        type=Path,
        default=Path("data/processed/hydral"),
        metavar="DIR",
        help="Root output directory (default: data/processed/hydral)",
    )
    p_pr.add_argument("--normalize", action="store_true", help="Peak-normalize audio")
    p_pr.add_argument(
        "--band-split",
        action="store_true",
        help="Split into frequency bands (tonal + noise per band)",
    )
    p_pr.add_argument(
        "--grain",
        action="store_true",
        help="Granular shuffle and reassemble",
    )
    p_pr.add_argument(
        "--grain-sec",
        type=float,
        default=0.5,
        metavar="SEC",
        help="Grain length in seconds (default: 0.5)",
    )
    p_pr.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for grain shuffle (default: 42)",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "process":
        _cmd_process(args)


if __name__ == "__main__":
    main()
