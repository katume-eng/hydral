"""Unit tests for the hydral pipeline framework.

Tests focus on:
- PipelineContext construction
- Pipeline step chaining
- _collect_inputs helper
- Step Protocol conformance
"""
import json
import sys
import os
from pathlib import Path

# Ensure src/ is on the path (mirrors the pattern used in songmaking tests)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import soundfile as sf
import pytest

from hydral.pipeline import Pipeline, PipelineContext, Step


# ── helpers ─────────────────────────────────────────────────────────────────

def _make_wav(path: Path, duration_sec: float = 1.0, sr: int = 22050) -> None:
    """Write a simple sine-wave WAV for testing."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), dtype=np.float32)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), audio, sr)


# ── PipelineContext ──────────────────────────────────────────────────────────

def test_pipeline_context_defaults(tmp_path):
    ctx = PipelineContext(input_path=tmp_path / "in.wav", output_dir=tmp_path / "out")
    assert ctx.sample_rate is None
    assert ctx.extra == {}


# ── Pipeline chaining ────────────────────────────────────────────────────────

class _RecordingStep:
    """A test step that appends its name to ctx.extra['log']."""
    def __init__(self, name: str):
        self.name = name

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.extra.setdefault("log", []).append(self.name)
        return ctx


def test_pipeline_runs_steps_in_order(tmp_path):
    ctx = PipelineContext(input_path=tmp_path / "in.wav", output_dir=tmp_path / "out")
    pipeline = Pipeline([_RecordingStep("a"), _RecordingStep("b"), _RecordingStep("c")])
    result = pipeline.run(ctx)
    assert result.extra["log"] == ["a", "b", "c"]


def test_empty_pipeline_is_noop(tmp_path):
    ctx = PipelineContext(input_path=tmp_path / "in.wav", output_dir=tmp_path / "out")
    result = Pipeline([]).run(ctx)
    assert result.extra == {}


def test_step_protocol_conformance():
    assert isinstance(_RecordingStep("x"), Step)


# ── AnalyzeStep ──────────────────────────────────────────────────────────────

def test_analyze_step_creates_json(tmp_path):
    wav = tmp_path / "tone.wav"
    _make_wav(wav)
    out_dir = tmp_path / "out"

    from hydral.steps import AnalyzeStep
    ctx = PipelineContext(input_path=wav, output_dir=out_dir)
    AnalyzeStep().run(ctx)

    json_path = out_dir / "tone_features.json"
    assert json_path.exists(), "features JSON not created"
    with open(json_path) as fh:
        data = json.load(fh)
    assert "rms" in data
    assert "low" in data
    assert "mid" in data
    assert "high" in data
    assert "onset" in data
    assert "meta" in data
    assert isinstance(data["rms"], list)
    assert ctx.extra.get("features_path") == json_path


# ── NormalizeStep ────────────────────────────────────────────────────────────

def test_normalize_step_creates_wav(tmp_path):
    wav = tmp_path / "tone.wav"
    _make_wav(wav)
    out_dir = tmp_path / "out"

    from hydral.steps import NormalizeStep
    ctx = PipelineContext(input_path=wav, output_dir=out_dir)
    NormalizeStep(target_db=-1.0).run(ctx)

    out_wav = out_dir / "tone_normalized.wav"
    assert out_wav.exists(), "normalized WAV not created"
    audio, _ = sf.read(str(out_wav))
    peak_db = 20 * np.log10(np.abs(audio).max())
    assert abs(peak_db - (-1.0)) < 0.1, f"Peak {peak_db:.2f} dB, expected -1.0 dB"


# ── GrainStep ────────────────────────────────────────────────────────────────

def test_grain_step_creates_wav(tmp_path):
    wav = tmp_path / "tone.wav"
    _make_wav(wav, duration_sec=2.0)
    out_dir = tmp_path / "out"

    from hydral.steps import GrainStep
    ctx = PipelineContext(input_path=wav, output_dir=out_dir)
    GrainStep(grain_sec=0.5, seed=42).run(ctx)

    out_wav = out_dir / "tone_grain.wav"
    assert out_wav.exists(), "grain WAV not created"


# ── _collect_inputs ──────────────────────────────────────────────────────────

def test_collect_inputs_single_file(tmp_path):
    from hydral.__main__ import _collect_inputs
    wav = tmp_path / "track.wav"
    wav.touch()
    result = _collect_inputs(wav)
    assert result == [wav]


def test_collect_inputs_folder(tmp_path):
    from hydral.__main__ import _collect_inputs
    (tmp_path / "a.wav").touch()
    (tmp_path / "b.wav").touch()
    (tmp_path / "readme.txt").touch()  # should be filtered out
    result = _collect_inputs(tmp_path)
    assert len(result) == 2
    assert all(p.suffix == ".wav" for p in result)


def test_collect_inputs_mp3_flac(tmp_path):
    from hydral.__main__ import _collect_inputs
    (tmp_path / "a.mp3").touch()
    (tmp_path / "b.flac").touch()
    result = _collect_inputs(tmp_path)
    assert len(result) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
