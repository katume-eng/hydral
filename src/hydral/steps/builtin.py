"""Built-in pipeline steps for hydral.

Each step extends :class:`~hydral.steps.base.BaseStep`, calls the existing
processing/analysis implementations, fills :class:`~hydral.artifacts.Artifacts`,
and—for *transform* steps—updates ``ctx.audio_path`` so the next step in the
pipeline receives the transformed audio as input.

Steps read audio from ``ctx.audio_path`` (not ``ctx.input_path``) so that a
chain like ``normalize → grain`` will grain-process the *normalised* audio.
Output files are always named after ``ctx.input_path.stem`` for stable,
predictable file names regardless of chain depth.

All four built-in steps are registered in :data:`~hydral.steps.registry.StepRegistry`
at the bottom of this module.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import soundfile as sf

from hydral.analysis.audio_features.bands import extract_frequency_band_energies
from hydral.analysis.audio_features.etract_energy import extract_rms_energy
from hydral.analysis.audio_features.io import load_audio_waveform
from hydral.analysis.audio_features.onset import extract_onset_strength
from hydral.analysis.audio_features.smoothing import apply_moving_average
from hydral.infra.audio import export_wav, load_wav
from hydral.pipeline import PipelineContext
from hydral.processing.assemble import concat
from hydral.processing.band_split.split import split_into_bands
from hydral.processing.grain import split_grains
from hydral.processing.transform_mics import shuffle
from hydral.steps.base import BaseStep
from hydral.steps.registry import StepRegistry


# ── AnalyzeStep ────────────────────────────────────────────────────────────


class AnalyzeStep(BaseStep):
    """Extract audio features and save them as ``<stem>_features.json``.

    Reads from ``ctx.audio_path`` but does *not* update it (analysis is
    non-destructive).
    """

    def __init__(
        self,
        hop_length: int = 512,
        smoothing_window: int = 5,
        sr: int | None = None,
    ) -> None:
        self.hop_length = hop_length
        self.smoothing_window = smoothing_window
        self.sr = sr

    @property
    def step_name(self) -> str:
        return "analyze"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        return [ctx.output_dir / f"{ctx.input_path.stem}_features.json"]

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        fp = super().fingerprint(ctx)
        fp["params"] = {
            "hop_length": self.hop_length,
            "smoothing_window": self.smoothing_window,
            "sr": self.sr,
        }
        return fp

    def output_exists(self, ctx: PipelineContext) -> bool:
        return (ctx.output_dir / f"{ctx.input_path.stem}_features.json").exists()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        effective_sr = ctx.sample_rate if ctx.sample_rate is not None else self.sr
        waveform, sr = load_audio_waveform(ctx.audio_path, target_sample_rate=effective_sr)

        rms = extract_rms_energy(waveform, hop_length=self.hop_length)
        bands = extract_frequency_band_energies(waveform, sr, hop_length=self.hop_length)
        onset = extract_onset_strength(waveform, sr, hop_length=self.hop_length)

        rms = apply_moving_average(rms, window_size=self.smoothing_window)
        for k in bands:
            bands[k] = apply_moving_average(bands[k], window_size=self.smoothing_window)
        onset = apply_moving_average(onset, window_size=3)

        features: dict = {
            "rms": rms.tolist(),
            "low": bands["low"].tolist(),
            "mid": bands["mid"].tolist(),
            "high": bands["high"].tolist(),
            "onset": onset.tolist(),
            "meta": {
                "sample_rate": sr,
                "hop_length": self.hop_length,
                "num_frames": len(rms),
            },
        }

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_features.json"
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(features, fh, indent=2)

        print(f"  ✓ Features saved to {out_path}")
        ctx.artifacts.features_json = out_path
        ctx.extra["features_path"] = out_path  # backward compat
        return ctx


# ── NormalizeStep ──────────────────────────────────────────────────────────


class NormalizeStep(BaseStep):
    """Peak-normalize audio and save it as ``<stem>_normalized.wav``.

    Reads from ``ctx.audio_path`` and updates ``ctx.audio_path`` to the
    normalised file so downstream transform steps use the normalised audio.
    """

    def __init__(self, target_db: float = -1.0) -> None:
        self.target_db = target_db

    @property
    def step_name(self) -> str:
        return "normalize"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        return [ctx.output_dir / f"{ctx.input_path.stem}_normalized.wav"]

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        fp = super().fingerprint(ctx)
        fp["params"] = {"target_db": self.target_db}
        return fp

    def output_exists(self, ctx: PipelineContext) -> bool:
        return (ctx.output_dir / f"{ctx.input_path.stem}_normalized.wav").exists()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        audio, sr = sf.read(str(ctx.audio_path), always_2d=False)
        peak = float(np.abs(audio).max())
        if peak > 0:
            target_linear = 10 ** (self.target_db / 20.0)
            audio = audio * (target_linear / peak)

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_normalized.wav"
        sf.write(str(out_path), audio, sr, subtype="FLOAT")

        print(f"  ✓ Normalized audio saved to {out_path}")
        ctx.artifacts.normalized_wav = out_path
        ctx.extra["normalized_path"] = out_path  # backward compat
        ctx.audio_path = out_path  # pipe: next step reads normalised audio
        return ctx


# ── BandSplitStep ──────────────────────────────────────────────────────────


class BandSplitStep(BaseStep):
    """Split audio into frequency bands.

    Wraps :func:`~hydral.processing.band_split.split.split_into_bands`.
    Reads from ``ctx.audio_path`` and updates ``ctx.audio_path`` to the
    band directory (a directory path, not a WAV) so downstream steps are
    aware of the transformation.
    """

    def __init__(self, filter_order: int = 5) -> None:
        self.filter_order = filter_order

    @property
    def step_name(self) -> str:
        return "band_split"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        band_dir = ctx.output_dir / f"{ctx.input_path.stem}_bands"
        return [band_dir]

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        fp = super().fingerprint(ctx)
        fp["params"] = {"filter_order": self.filter_order}
        return fp

    def output_exists(self, ctx: PipelineContext) -> bool:
        band_dir = ctx.output_dir / f"{ctx.input_path.stem}_bands"
        return band_dir.is_dir() and any(band_dir.iterdir())

    def run(self, ctx: PipelineContext) -> PipelineContext:
        band_dir = ctx.output_dir / f"{ctx.input_path.stem}_bands"
        manifest = split_into_bands(
            input_path=ctx.audio_path,
            output_dir=band_dir,
            filter_order=self.filter_order,
        )

        # Write manifest JSON alongside the band files
        manifest_path = band_dir / "split_manifest.json"

        print(f"  ✓ Band split saved to {band_dir} ({len(manifest['outputs'])} files)")
        ctx.artifacts.band_dir = band_dir
        ctx.artifacts.band_manifest_json = manifest_path
        ctx.extra["band_split_manifest"] = manifest  # backward compat
        ctx.audio_path = band_dir  # pipe: signal that audio is now split
        return ctx


# ── GrainStep ──────────────────────────────────────────────────────────────


class GrainStep(BaseStep):
    """Shuffle audio grains and reassemble as ``<stem>_grain.wav``.

    Reads from ``ctx.audio_path`` and updates ``ctx.audio_path`` to the
    grain-processed file.
    """

    def __init__(self, grain_sec: float = 0.5, seed: int = 42) -> None:
        self.grain_sec = grain_sec
        self.seed = seed

    @property
    def step_name(self) -> str:
        return "grain"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        return [ctx.output_dir / f"{ctx.input_path.stem}_grain.wav"]

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        fp = super().fingerprint(ctx)
        fp["params"] = {"grain_sec": self.grain_sec, "seed": self.seed}
        return fp

    def output_exists(self, ctx: PipelineContext) -> bool:
        return (ctx.output_dir / f"{ctx.input_path.stem}_grain.wav").exists()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        audio = load_wav(ctx.audio_path)
        grain_ms = int(self.grain_sec * 1000)
        grains = split_grains(audio, grain_ms)
        grains = shuffle(grains, seed=self.seed)
        assembled = concat(grains)

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_grain.wav"
        export_wav(assembled, out_path)

        print(f"  ✓ Grain-processed audio saved to {out_path}")
        ctx.artifacts.grain_wav = out_path
        ctx.extra["grain_path"] = out_path  # backward compat
        ctx.audio_path = out_path  # pipe: next step reads grain audio
        return ctx


# ── Registration ───────────────────────────────────────────────────────────

def _register_builtins() -> None:
    StepRegistry.register("analyze", AnalyzeStep)
    StepRegistry.register("normalize", NormalizeStep)
    StepRegistry.register("band_split", BandSplitStep)
    StepRegistry.register("grain", GrainStep)


_register_builtins()
