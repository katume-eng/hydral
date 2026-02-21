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


# ── yaml_runner ──────────────────────────────────────────────────────────────

def _write_pipeline_yaml(path: Path, extra: str = "") -> None:
    """Write a minimal pipeline YAML for testing."""
    path.write_text(
        "pipeline:\n"
        "  name: test_pipeline\n"
        "  input: data/raw\n"
        "  output: data/processed/hydral\n"
        "  steps:\n"
        "    - name: normalize\n"
        "      enabled: true\n"
        "      params:\n"
        "        target_db: -1.0\n"
        "    - name: analyze\n"
        "      enabled: false\n"
        + extra,
        encoding="utf-8",
    )


def test_load_config(tmp_path):
    from hydral.yaml_runner import load_config, PipelineConfig

    cfg_file = tmp_path / "pipeline.yaml"
    _write_pipeline_yaml(cfg_file)
    cfg = load_config(cfg_file)
    assert isinstance(cfg, PipelineConfig)
    assert cfg.name == "test_pipeline"
    assert len(cfg.steps) == 2
    assert cfg.steps[0].name == "normalize"
    assert cfg.steps[0].enabled is True
    assert cfg.steps[1].name == "analyze"
    assert cfg.steps[1].enabled is False


def test_collect_inputs_yaml_runner_file(tmp_path):
    from hydral.yaml_runner import collect_inputs

    wav = tmp_path / "track.wav"
    wav.touch()
    result = collect_inputs(wav, ["**/*.wav"])
    assert result == [wav]


def test_collect_inputs_yaml_runner_recursive(tmp_path):
    from hydral.yaml_runner import collect_inputs

    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "a.wav").touch()
    (sub / "b.flac").touch()
    (tmp_path / "c.wav").touch()
    result = collect_inputs(tmp_path, ["**/*.wav", "**/*.flac"])
    assert len(result) == 3


def test_collect_inputs_yaml_runner_missing_dir(tmp_path):
    from hydral.yaml_runner import collect_inputs

    result = collect_inputs(tmp_path / "missing", ["**/*.wav"])
    assert result == []


def test_build_step_known_names():
    from hydral.yaml_runner import StepConfig, build_step
    from hydral.steps import AnalyzeStep, BandSplitStep, GrainStep, NormalizeStep

    assert isinstance(build_step(StepConfig("analyze")), AnalyzeStep)
    assert isinstance(build_step(StepConfig("normalize")), NormalizeStep)
    assert isinstance(build_step(StepConfig("band_split")), BandSplitStep)
    assert isinstance(build_step(StepConfig("grain")), GrainStep)


def test_build_step_unknown_raises():
    from hydral.yaml_runner import StepConfig, build_step

    with pytest.raises(ValueError, match="Unknown step"):
        build_step(StepConfig("nonexistent"))


def test_run_pipeline_normalize_only(tmp_path):
    """Integration: run_pipeline with a single normalize step."""
    wav = tmp_path / "raw" / "tone.wav"
    wav.parent.mkdir(parents=True)
    _make_wav(wav)

    out_root = tmp_path / "out"
    cfg_file = tmp_path / "pipeline.yaml"
    cfg_file.write_text(
        f"pipeline:\n"
        f"  name: test\n"
        f"  input: {wav}\n"
        f"  output: {out_root}\n"
        f"  steps:\n"
        f"    - name: normalize\n"
        f"      enabled: true\n"
        f"      params:\n"
        f"        target_db: -1.0\n",
        encoding="utf-8",
    )

    from hydral.yaml_runner import run_pipeline

    run_pipeline(cfg_file)

    normalized = out_root / "tone" / "tone_normalized.wav"
    assert normalized.exists(), "normalized WAV not created"

    runs_dir = out_root / "_runs"
    reports = list(runs_dir.glob("run_*.json"))
    assert len(reports) == 1

    with open(reports[0], encoding="utf-8") as fh:
        report = json.load(fh)

    assert report["pipeline_name"] == "test"
    assert len(report["files"]) == 1
    assert report["files"][0]["status"] == "success"
    ran_steps = [s for s in report["files"][0]["steps"] if s["status"] == "ran"]
    assert len(ran_steps) == 1
    assert ran_steps[0]["name"] == "normalize"


def test_run_pipeline_disabled_step(tmp_path):
    """Disabled steps should appear in report with status 'skipped_disabled'."""
    wav = tmp_path / "tone.wav"
    _make_wav(wav)

    out_root = tmp_path / "out"
    cfg_file = tmp_path / "pipeline.yaml"
    cfg_file.write_text(
        f"pipeline:\n"
        f"  name: test\n"
        f"  input: {wav}\n"
        f"  output: {out_root}\n"
        f"  steps:\n"
        f"    - name: normalize\n"
        f"      enabled: false\n",
        encoding="utf-8",
    )

    from hydral.yaml_runner import run_pipeline

    run_pipeline(cfg_file)

    runs_dir = out_root / "_runs"
    reports = list(runs_dir.glob("run_*.json"))
    assert len(reports) == 1
    with open(reports[0], encoding="utf-8") as fh:
        report = json.load(fh)

    skipped = [s for s in report["files"][0]["steps"] if s["status"] == "skipped_disabled"]
    assert len(skipped) == 1


def test_run_pipeline_skips_existing_output(tmp_path):
    """A step whose output already exists should be skipped."""
    wav = tmp_path / "tone.wav"
    _make_wav(wav)

    out_root = tmp_path / "out"
    cfg_file = tmp_path / "pipeline.yaml"
    cfg_file.write_text(
        f"pipeline:\n"
        f"  name: test\n"
        f"  input: {wav}\n"
        f"  output: {out_root}\n"
        f"  steps:\n"
        f"    - name: normalize\n"
        f"      enabled: true\n",
        encoding="utf-8",
    )

    # Pre-create the output so the step is skipped
    pre_out = out_root / "tone" / "tone_normalized.wav"
    pre_out.parent.mkdir(parents=True)
    _make_wav(pre_out)

    from hydral.yaml_runner import run_pipeline

    run_pipeline(cfg_file)

    runs_dir = out_root / "_runs"
    reports = list(runs_dir.glob("run_*.json"))
    with open(reports[0], encoding="utf-8") as fh:
        report = json.load(fh)

    skipped = [s for s in report["files"][0]["steps"] if s["status"] == "skipped_exists"]
    assert len(skipped) == 1


def test_output_exists_methods(tmp_path):
    """output_exists() returns False before creation and True after."""
    from hydral.pipeline import PipelineContext
    from hydral.steps import AnalyzeStep, GrainStep, NormalizeStep

    wav = tmp_path / "tone.wav"
    _make_wav(wav)
    ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")

    normalize = NormalizeStep()
    analyze = AnalyzeStep()
    grain = GrainStep()

    assert normalize.output_exists(ctx) is False
    assert analyze.output_exists(ctx) is False
    assert grain.output_exists(ctx) is False

    normalize.run(ctx)
    assert normalize.output_exists(ctx) is True

    analyze.run(ctx)
    assert analyze.output_exists(ctx) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
