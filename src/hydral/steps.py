"""Built-in pipeline steps for hydral.

Each step receives a :class:`~hydral.pipeline.PipelineContext`, performs one
transformation, writes its output under ``ctx.output_dir``, and returns the
(potentially updated) context so the next step can consume it.
"""
from __future__ import annotations

import json
from pathlib import Path

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


class AnalyzeStep:
    """Extract audio features and save them as ``<stem>_features.json``."""

    def __init__(self, hop_length: int = 512, smoothing_window: int = 5) -> None:
        self.hop_length = hop_length
        self.smoothing_window = smoothing_window

    def run(self, ctx: PipelineContext) -> PipelineContext:
        waveform, sr = load_audio_waveform(
            ctx.input_path, target_sample_rate=ctx.sample_rate
        )

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
        ctx.extra["features_path"] = out_path
        return ctx


class NormalizeStep:
    """Peak-normalize audio and save it as ``<stem>_normalized.wav``."""

    def __init__(self, target_db: float = -1.0) -> None:
        self.target_db = target_db

    def run(self, ctx: PipelineContext) -> PipelineContext:
        audio, sr = sf.read(str(ctx.input_path), always_2d=False)
        peak = float(np.abs(audio).max())
        if peak > 0:
            target_linear = 10 ** (self.target_db / 20.0)
            audio = audio * (target_linear / peak)

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_normalized.wav"
        sf.write(str(out_path), audio, sr, subtype="FLOAT")

        print(f"  ✓ Normalized audio saved to {out_path}")
        ctx.extra["normalized_path"] = out_path
        return ctx


class BandSplitStep:
    """Split audio into frequency bands (wraps :func:`~hydral.processing.band_split.split.split_into_bands`)."""

    def __init__(self, filter_order: int = 5) -> None:
        self.filter_order = filter_order

    def run(self, ctx: PipelineContext) -> PipelineContext:
        band_dir = ctx.output_dir / f"{ctx.input_path.stem}_bands"
        manifest = split_into_bands(
            input_path=ctx.input_path,
            output_dir=band_dir,
            filter_order=self.filter_order,
        )

        print(f"  ✓ Band split saved to {band_dir} ({len(manifest['outputs'])} files)")
        ctx.extra["band_split_manifest"] = manifest
        return ctx


class GrainStep:
    """Split audio into grains, shuffle them, and reassemble as ``<stem>_grain.wav``."""

    def __init__(self, grain_sec: float = 0.5, seed: int = 42) -> None:
        self.grain_sec = grain_sec
        self.seed = seed

    def run(self, ctx: PipelineContext) -> PipelineContext:
        audio = load_wav(ctx.input_path)
        grain_ms = int(self.grain_sec * 1000)
        grains = split_grains(audio, grain_ms)
        grains = shuffle(grains, seed=self.seed)
        assembled = concat(grains)

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_grain.wav"
        export_wav(assembled, out_path)

        print(f"  ✓ Grain-processed audio saved to {out_path}")
        ctx.extra["grain_path"] = out_path
        return ctx
