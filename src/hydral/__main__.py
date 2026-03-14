"""python -m hydral  –  minimal pipeline runner for hydral.

Commands
--------
analyze
    Extract audio features (RMS, bands, onset) to JSON files under
    data/processed/hydral/<stem>/.

process
    Apply one or more audio transformations (normalize, band-split, grain)
    and write the results to data/processed/hydral/<stem>/.

instagram
    Normalize raw audio and export short clips for Instagram posts
    (default 24 s, multiple offset candidates) to data/exports/instagram/.

splash
    Detect instantaneous splash events in a WAV file and print them to
    stdout.  Optionally save as JSON with --json.

Examples
--------
Analyze every WAV in data/raw/::

    python -m hydral analyze data/raw/

Normalize + band-split a single file::

    python -m hydral process data/raw/track.wav --normalize --band-split

Granular shuffle with a custom output directory::

    python -m hydral process data/raw/track.wav --grain --out /tmp/out

Export Instagram clips from a folder::

    python -m hydral instagram data/raw --duration-sec 24 --offsets "0,5,10"

Export as MP3 without date subfolder::

    python -m hydral instagram data/raw/track.wav --format mp3 --no-date-subdir

Detect splash events in a WAV file::

    python -m hydral splash data/raw/splash.wav --json output.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SUPPORTED_EXTS = {".wav", ".mp3", ".flac"}
_IG_SUPPORTED_EXTS = {".wav", ".mp3", ".flac", ".m4a"}
_IG_DEFAULT_GLOBS = ["**/*.wav", "**/*.mp3", "**/*.flac", "**/*.m4a"]


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


def _collect_inputs_glob(src: Path, patterns: list[str]) -> list[Path]:
    """Return a sorted list of audio files from *src* using glob patterns."""
    if src.is_file():
        if src.suffix.lower() not in _IG_SUPPORTED_EXTS:
            sys.exit(f"Unsupported file type: {src.suffix!r}")
        return [src]
    if src.is_dir():
        seen: set[Path] = set()
        files: list[Path] = []
        for pattern in patterns:
            for p in src.glob(pattern):
                if p.is_file() and p not in seen:
                    seen.add(p)
                    files.append(p)
        return sorted(files)
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


def _cmd_run(args: argparse.Namespace) -> None:
    from hydral.yaml_runner import run_pipeline

    config_path = args.config
    if not config_path.exists():
        sys.exit(f"Config file not found: {config_path}")
    run_pipeline(config_path)


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


def _cmd_instagram(args: argparse.Namespace) -> None:  # noqa: C901
    import json
    from datetime import datetime, timezone

    from pydub import AudioSegment

    from hydral.pipeline import Pipeline, PipelineContext
    from hydral.steps import AnalyzeStep, NormalizeStep

    # ── resolve tool version ─────────────────────────────────────────────────
    try:
        from importlib.metadata import version as _pkg_version
        tool_version: str = _pkg_version("hydral")
    except Exception:
        tool_version = "dev"

    quiet: bool = args.quiet
    dry_run: bool = args.dry_run

    def _log(msg: str) -> None:
        if not quiet:
            print(msg)

    def _warn(msg: str) -> None:
        print(f"WARNING: {msg}", file=sys.stderr)

    # ── collect inputs ───────────────────────────────────────────────────────
    patterns: list[str] = args.glob if args.glob else _IG_DEFAULT_GLOBS
    input_files = _collect_inputs_glob(args.input, patterns)

    if not input_files:
        sys.exit(f"No audio files found in {args.input}")

    if args.limit is not None and args.limit > 0:
        input_files = input_files[: args.limit]

    # ── parse offsets ────────────────────────────────────────────────────────
    try:
        offsets: list[float] = [float(x.strip()) for x in args.offsets.split(",")]
    except ValueError:
        sys.exit(f"Invalid --offsets value: {args.offsets!r}")

    # ── determine output directory ───────────────────────────────────────────
    out_root = Path(args.out_dir)
    if args.date_subdir:
        date_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
        out_dir = out_root / date_str
    else:
        out_dir = out_root

    processed_root = Path(args.processed_out)

    _log(
        f"[instagram] {len(input_files)} file(s) → {out_dir}"
        + (" [DRY RUN]" if dry_run else "")
    )

    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # ── tracking counters ────────────────────────────────────────────────────
    reused_count = 0
    normalized_count = 0
    exported_count = 0
    errors: list[str] = []

    for idx, src in enumerate(input_files, 1):
        stem = src.stem
        _log(f"  [{idx}/{len(input_files)}] {src.name}")

        processed_dir = processed_root / stem
        normalized_path = processed_dir / f"{stem}_normalized.wav"

        # ── normalize step ───────────────────────────────────────────────────
        if normalized_path.exists() and not args.force:
            _log(f"    skip normalize (exists): {normalized_path}")
            reused_count += 1
        else:
            if dry_run:
                _log(f"    [dry-run] would normalize → {normalized_path}")
            else:
                try:
                    steps = []
                    if args.analyze:
                        steps.append(AnalyzeStep())
                    steps.append(NormalizeStep(target_db=args.target_db))
                    pipeline = Pipeline(steps)
                    ctx = PipelineContext(
                        input_path=src,
                        output_dir=processed_dir,
                        sample_rate=args.sr,
                    )
                    processed_dir.mkdir(parents=True, exist_ok=True)
                    pipeline.run(ctx)
                    normalized_count += 1
                except Exception as exc:
                    msg = f"{src.name}: normalize failed: {exc}"
                    _warn(msg)
                    errors.append(msg)
                    continue

        if dry_run:
            for offset in offsets:
                clip_name = f"{stem}_ig_{int(args.duration_sec)}s_{int(offset)}s"
                out_path = out_dir / f"{clip_name}.{args.format}"
                _log(f"    [dry-run] would export {out_path}")
            continue

        if not normalized_path.exists():
            msg = f"{src.name}: normalized file not found at {normalized_path}"
            _warn(msg)
            errors.append(msg)
            continue

        # ── load normalized audio ────────────────────────────────────────────
        try:
            import numpy as np
            import soundfile as sf

            # 1) FLOATで読む（ここが重要）
            float_data, file_sr = sf.read(str(normalized_path), dtype="float32", always_2d=True)

            # 2) [-1, 1] にクリップして int16 にスケール
            float_data = np.clip(float_data, -1.0, 1.0)
            int16_data = (float_data * 32767.0).astype(np.int16)

            channels = int16_data.shape[1]

            audio = AudioSegment(
                int16_data.tobytes(),
                frame_rate=file_sr,
                sample_width=2,   # int16
                channels=channels,
            )

            if args.sr is not None:
                audio = audio.set_frame_rate(args.sr)

        except Exception as exc:
            msg = f"{src.name}: failed to load {normalized_path}: {exc}"
            _warn(msg)
            errors.append(msg)
            continue

        audio_duration_sec = len(audio) / 1000.0
        duration_ms = int(args.duration_sec * 1000)
        fade_in_ms: int = args.fade_in_ms
        fade_out_ms: int = args.fade_out_ms
        created_at = datetime.now(tz=timezone.utc).isoformat()

        # ── export clips ─────────────────────────────────────────────────────
        for offset in offsets:
            start_ms = int(offset * 1000)
            end_ms = start_ms + duration_ms

            if start_ms >= len(audio):
                _warn(
                    f"{src.name}: offset {offset}s exceeds audio length "
                    f"({audio_duration_sec:.1f}s), skipping"
                )
                continue

            if end_ms > len(audio):
                _warn(
                    f"{src.name}: offset {offset}s exceeds audio length "
                    f"({audio_duration_sec:.1f}s), skipping"
                )
                continue

            clip = audio[start_ms:end_ms]
            if fade_in_ms > 0:
                clip = clip.fade_in(min(fade_in_ms, len(clip)))
            if fade_out_ms > 0:
                clip = clip.fade_out(min(fade_out_ms, len(clip)))

            clip_name = f"{stem}_ig_{int(args.duration_sec)}s_{int(offset)}s"
            out_path = out_dir / f"{clip_name}.{args.format}"
            meta_path = out_dir / f"{clip_name}.json"

            try:
                if args.format == "mp3":
                    clip.export(str(out_path), format="mp3")
                else:
                    clip.export(str(out_path), format="wav")
            except Exception as exc:
                msg = f"{src.name}: export failed for offset {offset}s: {exc}"
                _warn(msg)
                errors.append(msg)
                continue

            exported_count += 1
            _log(f"    → {out_path.name}")

            # ── per-clip metadata JSON ────────────────────────────────────────
            meta: dict = {
                "source_path": str(src),
                "normalized_path": str(normalized_path),
                "exported_path": str(out_path),
                "start_sec": offset,
                "duration_sec": args.duration_sec,
                "fade_in_ms": fade_in_ms,
                "fade_out_ms": fade_out_ms,
                "target_db": args.target_db,
                "created_at": created_at,
                "tool_version": tool_version,
            }
            with open(meta_path, "w", encoding="utf-8") as fh:
                json.dump(meta, fh, ensure_ascii=False, indent=2)

            # ── _index.jsonl ─────────────────────────────────────────────────
            index_path = out_dir / "_index.jsonl"
            with open(index_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(meta, ensure_ascii=False) + "\n")

    # ── summary ──────────────────────────────────────────────────────────────
    _log("")
    _log("── Summary ──────────────────────────────────────────────")
    _log(f"  Input files    : {len(input_files)}")
    _log(f"  Reused (cached): {reused_count}")
    _log(f"  Newly normalized: {normalized_count}")
    _log(f"  Clips exported : {exported_count}")
    _log(f"  Output dir     : {out_dir}")
    if errors:
        _log(f"  Errors         : {len(errors)}")
        for e in errors:
            print(f"  ERROR: {e}", file=sys.stderr)
        sys.exit(1)


# ── splash ───────────────────────────────────────────────────────────────────

def _cmd_splash(args: argparse.Namespace) -> None:
    """Detect splash events in a single WAV file."""
    import json

    from hydral.analysis.audio_features.io import load_audio_waveform
    from hydral.analysis.events.splash import detect_splash_events, events_to_dicts

    wav_path = args.input
    if not wav_path.exists():
        sys.exit(f"File not found: {wav_path}")
    if wav_path.suffix.lower() not in _SUPPORTED_EXTS:
        sys.exit(f"Unsupported file type: {wav_path.suffix!r}")

    print(f"Loading {wav_path.name} …")
    y, sr = load_audio_waveform(wav_path, target_sample_rate=args.sr)

    print("Detecting splash events …")
    events = detect_splash_events(
        y,
        sr,
        hop_length=args.hop_length,
        smooth_window=args.smooth_window,
        energy_threshold_std=args.energy_threshold_std,
        onset_threshold_std=args.onset_threshold_std,
        min_interval_sec=args.min_interval_sec,
    )

    print(f"Found {len(events)} splash event(s).")
    preview = events[:10]
    for ev in preview:
        print(f"  t={ev.time_sec:.3f}s  strength={ev.strength:.4f}  sample={ev.sample_index}")
    if len(events) > 10:
        print(f"  … and {len(events) - 10} more.")

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(events_to_dicts(events), fh, ensure_ascii=False, indent=2)
        print(f"Saved JSON → {out_path}")


# ── argument parser ──────────────────────────────────────────────────────────

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m hydral",
        description="Hydral audio pipeline runner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ───────────────────────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run a YAML-configured pipeline")
    p_run.add_argument(
        "--config",
        type=Path,
        default=Path("pipeline.yaml"),
        metavar="FILE",
        help="Pipeline config file (default: pipeline.yaml)",
    )

    # ── analyze ───────────────────────────────────────────────────────────────
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

    # ── instagram ─────────────────────────────────────────────────────────────
    p_ig = sub.add_parser(
        "instagram",
        help="Export short clips from raw audio for Instagram posts",
    )
    p_ig.add_argument(
        "input",
        type=Path,
        nargs="?",
        default=Path("data/raw"),
        help="Input file or folder (default: data/raw)",
    )
    p_ig.add_argument(
        "--processed-out",
        type=Path,
        default=Path("data/processed/hydral"),
        metavar="DIR",
        help="Processed audio root directory (default: data/processed/hydral)",
    )
    p_ig.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/exports/instagram"),
        metavar="DIR",
        help="Export root directory (default: data/exports/instagram)",
    )
    p_ig.add_argument(
        "--date-subdir",
        dest="date_subdir",
        action="store_true",
        default=True,
        help="Append YYYYMMDD subfolder to output (default: on)",
    )
    p_ig.add_argument(
        "--no-date-subdir",
        dest="date_subdir",
        action="store_false",
        help="Disable date subfolder in output",
    )
    p_ig.add_argument(
        "--glob",
        action="append",
        metavar="PATTERN",
        help="Glob pattern for audio files (repeatable; default: wav/mp3/flac/m4a)",
    )
    p_ig.add_argument(
        "--duration-sec",
        type=float,
        default=24.0,
        metavar="SEC",
        help="Clip duration in seconds (default: 24)",
    )
    p_ig.add_argument(
        "--start-sec",
        type=float,
        default=0.0,
        metavar="SEC",
        help="Clip start offset in seconds (ignored when --offsets is set)",
    )
    p_ig.add_argument(
        "--offsets",
        type=str,
        default="0,5,10",
        metavar="CSV",
        help="Comma-separated start offsets in seconds (default: 0,5,10)",
    )
    p_ig.add_argument(
        "--fade-in-ms",
        type=int,
        default=50,
        metavar="MS",
        help="Fade-in duration in ms (default: 50)",
    )
    p_ig.add_argument(
        "--fade-out-ms",
        type=int,
        default=300,
        metavar="MS",
        help="Fade-out duration in ms (default: 300)",
    )
    p_ig.add_argument(
        "--target-db",
        type=float,
        default=-1.0,
        metavar="DB",
        help="Normalization target in dBFS (default: -1.0)",
    )
    p_ig.add_argument(
        "--analyze",
        dest="analyze",
        action="store_true",
        default=False,
        help="Run AnalyzeStep before normalizing",
    )
    p_ig.add_argument(
        "--no-analyze",
        dest="analyze",
        action="store_false",
        help="Skip analysis step (default)",
    )
    p_ig.add_argument(
        "--format",
        choices=["wav", "mp3"],
        default="wav",
        help="Output format (default: wav)",
    )
    p_ig.add_argument(
        "--sr",
        type=int,
        default=None,
        metavar="HZ",
        help="Resample clips to this sample rate (default: keep original)",
    )
    p_ig.add_argument(
        "--force",
        action="store_true",
        help="Re-process even if normalized file already exists",
    )
    p_ig.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing any files",
    )
    p_ig.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process only the first N input files",
    )
    p_ig.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output (errors are always shown)",
    )

    # ── splash ────────────────────────────────────────────────────────────────
    p_sp = sub.add_parser(
        "splash",
        help="Detect instantaneous splash events in a WAV file",
    )
    p_sp.add_argument("input", type=Path, help="Input WAV file")
    p_sp.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="Save detected events as JSON to this path",
    )
    p_sp.add_argument(
        "--sr",
        type=int,
        default=None,
        metavar="HZ",
        help="Resample to this sample rate before detection (default: keep original)",
    )
    p_sp.add_argument(
        "--hop-length",
        type=int,
        default=256,
        metavar="N",
        help="Analysis frame hop in samples (default: 256)",
    )
    p_sp.add_argument(
        "--smooth-window",
        type=int,
        default=5,
        metavar="N",
        help="Moving-average window for energy smoothing (default: 5)",
    )
    p_sp.add_argument(
        "--energy-threshold-std",
        type=float,
        default=2.0,
        metavar="K",
        help="Energy gate: mean + K×std (default: 2.0)",
    )
    p_sp.add_argument(
        "--onset-threshold-std",
        type=float,
        default=1.5,
        metavar="K",
        help="Onset gate: mean + K×std (default: 1.5)",
    )
    p_sp.add_argument(
        "--min-interval-sec",
        type=float,
        default=0.12,
        metavar="SEC",
        help="Refractory period between events in seconds (default: 0.12)",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "run":
        _cmd_run(args)
    elif args.command == "analyze":
        _cmd_analyze(args)
    elif args.command == "process":
        _cmd_process(args)
    elif args.command == "instagram":
        _cmd_instagram(args)
    elif args.command == "splash":
        _cmd_splash(args)


if __name__ == "__main__":
    main()
