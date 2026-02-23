"""Unit tests for the hydral instagram subcommand."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

# Ensure src/ is on the path (mirrors the pattern used in test_pipeline.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_wav(path: Path, duration_sec: float = 1.0, sr: int = 22050) -> None:
    """Write a simple sine-wave WAV for testing."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), dtype=np.float32)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), audio, sr)


def _run_instagram(argv: list[str]) -> None:
    """Run the instagram subcommand with the given argv."""
    from hydral.__main__ import _build_parser, _cmd_instagram

    parser = _build_parser()
    args = parser.parse_args(["instagram"] + argv)
    _cmd_instagram(args)


# ── tests ─────────────────────────────────────────────────────────────────────


def test_instagram_exports_clip_with_correct_duration(tmp_path: Path) -> None:
    """Exporting a 0.5-second clip from a 1-second WAV should produce a ~0.5 s file."""
    from pydub import AudioSegment

    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=1.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "0.5",
            "--offsets",
            "0",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
        ]
    )

    clips = list(out_dir.glob("*.wav"))
    assert len(clips) == 1, f"Expected 1 clip, got {len(clips)}"

    seg = AudioSegment.from_file(str(clips[0]))
    actual_sec = len(seg) / 1000.0
    assert abs(actual_sec - 0.5) < 0.05, f"Expected ~0.5 s, got {actual_sec:.3f} s"


def test_instagram_skips_out_of_range_offsets(tmp_path: Path) -> None:
    """Offsets that exceed the audio length must be skipped (no clip generated)."""
    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=1.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    # offsets: 0 (valid), 5 and 10 (both exceed 1-second audio)
    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "0.5",
            "--offsets",
            "0,5,10",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
        ]
    )

    clips = list(out_dir.glob("*.wav"))
    assert len(clips) == 1, f"Only offset 0 should be valid; got {len(clips)} clips"


def test_instagram_dry_run_creates_no_files(tmp_path: Path) -> None:
    """--dry-run must not create any output files."""
    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=2.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "1.0",
            "--offsets",
            "0,0.5",
            "--dry-run",
        ]
    )

    # out_dir must not have been created at all
    assert not out_dir.exists(), "dry-run must not create the output directory"


def test_instagram_creates_metadata_json(tmp_path: Path) -> None:
    """Each exported clip must have a companion .json metadata file."""
    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=2.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "1.0",
            "--offsets",
            "0",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
        ]
    )

    jsons = list(out_dir.glob("*.json"))
    # _index.jsonl is not a .json file, so this counts only clip metadata
    assert len(jsons) == 1, f"Expected 1 metadata JSON, got {len(jsons)}"

    with open(jsons[0], encoding="utf-8") as fh:
        meta = json.load(fh)

    for key in (
        "source_path",
        "normalized_path",
        "exported_path",
        "start_sec",
        "duration_sec",
        "fade_in_ms",
        "fade_out_ms",
        "target_db",
        "created_at",
        "tool_version",
    ):
        assert key in meta, f"Metadata missing key: {key!r}"


def test_instagram_creates_index_jsonl(tmp_path: Path) -> None:
    """_index.jsonl must contain one line per exported clip."""
    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=2.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "1.0",
            "--offsets",
            "0,0.5",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
        ]
    )

    index = out_dir / "_index.jsonl"
    assert index.exists(), "_index.jsonl not created"
    lines = [l for l in index.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 2, f"Expected 2 index entries, got {len(lines)}"


def test_instagram_reuses_existing_normalized(tmp_path: Path) -> None:
    """If the normalized file already exists, it must be reused (not re-created)."""
    src = tmp_path / "track.wav"
    _make_wav(src, duration_sec=2.0)

    stem = src.stem
    processed_dir = tmp_path / "processed" / "hydral"
    normalized_path = processed_dir / stem / f"{stem}_normalized.wav"
    normalized_path.parent.mkdir(parents=True)
    _make_wav(normalized_path, duration_sec=2.0)

    mtime_before = normalized_path.stat().st_mtime

    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(src),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "1.0",
            "--offsets",
            "0",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
        ]
    )

    mtime_after = normalized_path.stat().st_mtime
    assert mtime_before == mtime_after, "Normalized file was unexpectedly re-created"


def test_instagram_glob_collects_recursive(tmp_path: Path) -> None:
    """Files inside subdirectories must be collected when --glob uses **."""
    from hydral.__main__ import _collect_inputs_glob

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.wav").touch()
    (tmp_path / "b.wav").touch()
    (tmp_path / "ignore.txt").touch()

    results = _collect_inputs_glob(tmp_path, ["**/*.wav"])
    assert len(results) == 2
    assert all(p.suffix == ".wav" for p in results)


def test_instagram_limit(tmp_path: Path) -> None:
    """--limit N must process only N input files."""
    for i in range(3):
        _make_wav(tmp_path / f"track{i}.wav", duration_sec=1.0)

    processed_dir = tmp_path / "processed" / "hydral"
    out_dir = tmp_path / "exports"

    _run_instagram(
        [
            str(tmp_path),
            "--processed-out",
            str(processed_dir),
            "--out-dir",
            str(out_dir),
            "--no-date-subdir",
            "--duration-sec",
            "0.5",
            "--offsets",
            "0",
            "--fade-in-ms",
            "0",
            "--fade-out-ms",
            "0",
            "--limit",
            "2",
        ]
    )

    clips = list(out_dir.glob("*.wav"))
    assert len(clips) == 2, f"Expected 2 clips (limit=2), got {len(clips)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
