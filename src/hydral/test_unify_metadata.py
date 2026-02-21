"""Tests for processing/unify_metadata.py and EnsureMetadataStep."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np
import pytest
import soundfile as sf

from hydral.pipeline import PipelineContext


# ── helpers ──────────────────────────────────────────────────────────────────


def _make_wav(path: Path, duration_sec: float = 1.0, sr: int = 22050) -> None:
    """Write a simple sine-wave WAV for testing."""
    t = np.linspace(0, duration_sec, int(sr * duration_sec), dtype=np.float32)
    audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(str(path), audio, sr)


# ── unify_metadata module ─────────────────────────────────────────────────────


class TestIsV1:
    def test_valid_v1_returns_true(self):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, is_v1

        data = {
            "schema_version": SCHEMA_VERSION,
            "filename": "foo.wav",
            "duration_sec": 1.0,
            "sample_rate": 44100,
            "channels": 1,
            "tags": [],
        }
        assert is_v1(data) is True

    def test_missing_schema_version_returns_false(self):
        from hydral.processing.unify_metadata import is_v1

        data = {
            "filename": "foo.wav",
            "duration_sec": 1.0,
            "sample_rate": 44100,
            "channels": 1,
            "tags": [],
        }
        assert is_v1(data) is False

    def test_wrong_schema_version_returns_false(self):
        from hydral.processing.unify_metadata import is_v1

        data = {
            "schema_version": "v0",
            "filename": "foo.wav",
            "duration_sec": 1.0,
            "sample_rate": 44100,
            "channels": 1,
            "tags": [],
        }
        assert is_v1(data) is False

    def test_non_dict_returns_false(self):
        from hydral.processing.unify_metadata import is_v1

        assert is_v1(None) is False  # type: ignore[arg-type]
        assert is_v1([]) is False  # type: ignore[arg-type]

    def test_empty_dict_returns_false(self):
        from hydral.processing.unify_metadata import is_v1

        assert is_v1({}) is False


class TestToV1:
    def test_creates_v1_from_wav(self, tmp_path):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, is_v1, to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav, sr=44100)
        doc = to_v1(wav)
        assert doc["schema_version"] == SCHEMA_VERSION
        assert doc["filename"] == "test.wav"
        assert doc["sample_rate"] == 44100
        assert doc["channels"] == 1
        assert isinstance(doc["duration_sec"], float)
        assert doc["tags"] == []
        assert is_v1(doc)

    def test_preserves_existing_tags(self, tmp_path):
        from hydral.processing.unify_metadata import to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav)
        doc = to_v1(wav, existing={"tags": ["water", "rain"]})
        assert doc["tags"] == ["water", "rain"]

    def test_migrates_legacy_duration_alias(self, tmp_path):
        from hydral.processing.unify_metadata import to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav, duration_sec=2.0)
        doc = to_v1(wav, existing={"duration": 2.0, "tags": ["x"]})
        assert "duration_sec" in doc
        assert "duration" not in doc

    def test_migrates_legacy_rms_alias(self, tmp_path):
        from hydral.processing.unify_metadata import to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav)
        doc = to_v1(wav, existing={"rms": -43.0})
        assert doc["mean_rms"] == -43.0

    def test_overrides_schema_version_always(self, tmp_path):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav)
        doc = to_v1(wav, existing={"schema_version": "v0"})
        assert doc["schema_version"] == SCHEMA_VERSION

    def test_overrides_filename_always(self, tmp_path):
        from hydral.processing.unify_metadata import to_v1

        wav = tmp_path / "test.wav"
        _make_wav(wav)
        doc = to_v1(wav, existing={"filename": "wrong.wav"})
        assert doc["filename"] == "test.wav"


class TestEnsureMetadata:
    def test_creates_sidecar_when_absent(self, tmp_path):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, ensure_metadata

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        json_path, changed = ensure_metadata(wav)
        assert changed is True
        assert json_path == wav.with_suffix(".json")
        assert json_path.exists()
        with open(json_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        assert doc["schema_version"] == SCHEMA_VERSION

    def test_skips_when_already_v1(self, tmp_path):
        from hydral.processing.unify_metadata import (
            SCHEMA_VERSION,
            ensure_metadata,
            to_v1,
        )

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        # Pre-create a valid v1 sidecar
        sidecar = wav.with_suffix(".json")
        doc = to_v1(wav)
        with open(sidecar, "w", encoding="utf-8") as fh:
            json.dump(doc, fh)

        _, changed = ensure_metadata(wav)
        assert changed is False

    def test_updates_legacy_sidecar(self, tmp_path):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, ensure_metadata

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        # Write a legacy sidecar (no schema_version)
        sidecar = wav.with_suffix(".json")
        with open(sidecar, "w", encoding="utf-8") as fh:
            json.dump({"duration_sec": 1.0, "tags": ["old"]}, fh)

        json_path, changed = ensure_metadata(wav)
        assert changed is True
        with open(json_path, encoding="utf-8") as fh:
            doc = json.load(fh)
        assert doc["schema_version"] == SCHEMA_VERSION
        assert doc["tags"] == ["old"]

    def test_updates_corrupt_sidecar(self, tmp_path):
        from hydral.processing.unify_metadata import SCHEMA_VERSION, ensure_metadata

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        sidecar = wav.with_suffix(".json")
        sidecar.write_text("not json!", encoding="utf-8")

        _, changed = ensure_metadata(wav)
        assert changed is True
        with open(sidecar, encoding="utf-8") as fh:
            doc = json.load(fh)
        assert doc["schema_version"] == SCHEMA_VERSION


class TestMigrateRoot:
    def test_migrates_all_wavs_in_tree(self, tmp_path):
        from hydral.processing.unify_metadata import migrate_root

        sub = tmp_path / "sub"
        sub.mkdir()
        wavs = [tmp_path / "a.wav", sub / "b.wav"]
        for w in wavs:
            _make_wav(w)

        counts = migrate_root(tmp_path)
        assert counts["created"] == 2
        assert counts["updated"] == 0
        assert counts["skipped"] == 0

    def test_skips_already_v1(self, tmp_path):
        from hydral.processing.unify_metadata import ensure_metadata, migrate_root

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        ensure_metadata(wav)  # create v1 first

        counts = migrate_root(tmp_path)
        assert counts["skipped"] == 1
        assert counts["created"] == 0

    def test_updates_legacy(self, tmp_path):
        from hydral.processing.unify_metadata import migrate_root

        wav = tmp_path / "track.wav"
        _make_wav(wav)
        wav.with_suffix(".json").write_text('{"tags": ["old"]}', encoding="utf-8")

        counts = migrate_root(tmp_path)
        assert counts["updated"] == 1
        assert counts["created"] == 0
        assert counts["skipped"] == 0


# ── EnsureMetadataStep ─────────────────────────────────────────────────────────


class TestEnsureMetadataStep:
    def test_creates_sidecar_json(self, tmp_path):
        from hydral.steps import EnsureMetadataStep

        wav = tmp_path / "tone.wav"
        _make_wav(wav)
        ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")
        EnsureMetadataStep().run(ctx)

        sidecar = wav.with_suffix(".json")
        assert sidecar.exists()
        with open(sidecar, encoding="utf-8") as fh:
            doc = json.load(fh)
        from hydral.processing.unify_metadata import SCHEMA_VERSION
        assert doc["schema_version"] == SCHEMA_VERSION

    def test_fills_artifacts_metadata_json(self, tmp_path):
        from hydral.steps import EnsureMetadataStep

        wav = tmp_path / "tone.wav"
        _make_wav(wav)
        ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")
        EnsureMetadataStep().run(ctx)

        assert ctx.artifacts.metadata_json == wav.with_suffix(".json")

    def test_does_not_update_audio_path(self, tmp_path):
        from hydral.steps import EnsureMetadataStep

        wav = tmp_path / "tone.wav"
        _make_wav(wav)
        ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")
        EnsureMetadataStep().run(ctx)

        assert ctx.audio_path == wav

    def test_output_exists_false_before_run(self, tmp_path):
        from hydral.steps import EnsureMetadataStep

        wav = tmp_path / "tone.wav"
        _make_wav(wav)
        ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")
        step = EnsureMetadataStep()
        assert step.output_exists(ctx) is False

    def test_output_exists_true_after_run(self, tmp_path):
        from hydral.steps import EnsureMetadataStep

        wav = tmp_path / "tone.wav"
        _make_wav(wav)
        ctx = PipelineContext(input_path=wav, output_dir=tmp_path / "out")
        step = EnsureMetadataStep()
        step.run(ctx)
        assert step.output_exists(ctx) is True

    def test_registered_in_registry(self):
        from hydral.steps.registry import StepRegistry

        assert "ensure_metadata" in StepRegistry.names()

    def test_step_registry_build_returns_correct_type(self):
        from hydral.steps import EnsureMetadataStep
        from hydral.steps.registry import StepRegistry

        step = StepRegistry.build("ensure_metadata")
        assert isinstance(step, EnsureMetadataStep)

    def test_run_pipeline_with_ensure_metadata(self, tmp_path):
        """Integration: run_pipeline with ensure_metadata as first step."""
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
            f"    - name: ensure_metadata\n"
            f"      enabled: true\n"
            f"    - name: normalize\n"
            f"      enabled: true\n"
            f"      params:\n"
            f"        target_db: -1.0\n",
            encoding="utf-8",
        )

        from hydral.yaml_runner import run_pipeline

        run_pipeline(cfg_file)

        # Sidecar should be created next to the input WAV
        sidecar = wav.with_suffix(".json")
        assert sidecar.exists(), "sidecar JSON not created next to input WAV"
        with open(sidecar, encoding="utf-8") as fh:
            doc = json.load(fh)
        from hydral.processing.unify_metadata import SCHEMA_VERSION
        assert doc["schema_version"] == SCHEMA_VERSION

        # Normalize output should also exist
        normalized = out_root / "tone" / "tone_normalized.wav"
        assert normalized.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
