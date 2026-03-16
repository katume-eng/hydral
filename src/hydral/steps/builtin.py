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
from hydral.analysis.events.splash import (
    compute_energy_envelope,
    compute_onset_envelope,
    detect_splash_events,
    events_to_dicts,
)
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

    # Block size for streaming I/O: 65536 frames balances memory usage (~1 MB
    # per channel at float32) against I/O syscall overhead.
    _BLOCK_FRAMES: int = 65536

    def run(self, ctx: PipelineContext) -> PipelineContext:
        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        out_path = ctx.output_dir / f"{ctx.input_path.stem}_normalized.wav"

        target_linear = 10 ** (self.target_db / 20.0)

        with sf.SoundFile(str(ctx.audio_path)) as src:
            sr = src.samplerate
            channels = src.channels

            # 1st pass: find peak across all blocks
            peak = 0.0
            for block in src.blocks(blocksize=self._BLOCK_FRAMES, dtype="float32"):
                block_peak = float(np.max(np.abs(block)))
                if block_peak > peak:
                    peak = block_peak

            scale = (target_linear / peak) if peak > 0 else 1.0

            # 2nd pass: re-read, scale, and write
            src.seek(0)
            with sf.SoundFile(
                str(out_path),
                mode="w",
                samplerate=sr,
                channels=channels,
                subtype="FLOAT",
                format="WAV",
            ) as dst:
                for block in src.blocks(blocksize=self._BLOCK_FRAMES, dtype="float32"):
                    dst.write(block * scale)

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


# ── EnsureMetadataStep ─────────────────────────────────────────────────────


class EnsureMetadataStep(BaseStep):
    """Ensure a v1 sidecar metadata JSON exists alongside the input WAV.

    Reads ``ctx.audio_path``, delegates to
    :func:`~hydral.processing.unify_metadata.ensure_metadata`, and stores
    the sidecar path in ``ctx.artifacts.metadata_json``.

    This step is non-destructive: it does *not* modify ``ctx.audio_path``.
    It is intended to run *before* other transform steps so that all
    downstream processing has access to validated metadata.
    """

    @property
    def step_name(self) -> str:
        return "ensure_metadata"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        return [ctx.audio_path.with_suffix(".json")]

    def output_exists(self, ctx: PipelineContext) -> bool:
        from hydral.processing.unify_metadata import _sidecar_path, is_v1
        sidecar = _sidecar_path(ctx.audio_path)
        if not sidecar.exists():
            return False
        try:
            with open(sidecar, encoding="utf-8") as fh:
                data = json.load(fh)
            return is_v1(data)
        except (json.JSONDecodeError, OSError):
            return False

    def run(self, ctx: PipelineContext) -> PipelineContext:
        from hydral.processing.unify_metadata import _sidecar_path, ensure_metadata
        sidecar_existed = _sidecar_path(ctx.audio_path).exists()
        json_path, changed = ensure_metadata(ctx.audio_path)
        if changed:
            action = "migrated" if sidecar_existed else "created"
        else:
            action = "already v1"
        print(f"  ✓ Metadata sidecar {action}: {json_path}")
        ctx.artifacts.metadata_json = json_path
        return ctx



# ── SplashStep ─────────────────────────────────────────────────────────────


class SplashStep(BaseStep):
    """Detect splash events and save results as JSON and a debug PNG.

    Outputs:

    * ``<stem>_splash_events.json`` – list of detected events
      (time_sec, strength, sample_index).
    * ``<stem>_splash_debug.png`` – visualization of the energy/onset
      envelopes with vertical lines marking each event.

    Reads from ``ctx.audio_path`` but does *not* update it (analysis is
    non-destructive).
    """

    def __init__(
        self,
        hop_length: int = 256,
        smooth_window: int = 5,
        energy_threshold_std: float = 2.0,
        onset_threshold_std: float = 1.5,
        min_interval_sec: float = 0.12,
        sr: int | None = None,
    ) -> None:
        self.hop_length = hop_length
        self.smooth_window = smooth_window
        self.energy_threshold_std = energy_threshold_std
        self.onset_threshold_std = onset_threshold_std
        self.min_interval_sec = min_interval_sec
        self.sr = sr

    @property
    def step_name(self) -> str:
        return "splash"

    def outputs(self, ctx: PipelineContext) -> List[Path]:
        stem = ctx.input_path.stem
        return [
            ctx.output_dir / f"{stem}_splash_events.json",
            ctx.output_dir / f"{stem}_splash_debug.png",
        ]

    def fingerprint(self, ctx: PipelineContext) -> Dict[str, Any]:
        fp = super().fingerprint(ctx)
        fp["params"] = {
            "hop_length": self.hop_length,
            "smooth_window": self.smooth_window,
            "energy_threshold_std": self.energy_threshold_std,
            "onset_threshold_std": self.onset_threshold_std,
            "min_interval_sec": self.min_interval_sec,
            "sr": self.sr,
        }
        return fp

    def output_exists(self, ctx: PipelineContext) -> bool:
        stem = ctx.input_path.stem
        json_out = ctx.output_dir / f"{stem}_splash_events.json"
        png_out = ctx.output_dir / f"{stem}_splash_debug.png"
        return json_out.exists() and png_out.exists()

    def run(self, ctx: PipelineContext) -> PipelineContext:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        effective_sr = ctx.sample_rate if ctx.sample_rate is not None else self.sr
        waveform, sr = load_audio_waveform(ctx.audio_path, target_sample_rate=effective_sr)

        events = detect_splash_events(
            waveform,
            sr,
            hop_length=self.hop_length,
            smooth_window=self.smooth_window,
            energy_threshold_std=self.energy_threshold_std,
            onset_threshold_std=self.onset_threshold_std,
            min_interval_sec=self.min_interval_sec,
        )

        ctx.output_dir.mkdir(parents=True, exist_ok=True)
        stem = ctx.input_path.stem

        # ── Save JSON ─────────────────────────────────────────────────────────
        json_path = ctx.output_dir / f"{stem}_splash_events.json"
        with open(json_path, "w", encoding="utf-8") as fh:
            json.dump(events_to_dicts(events), fh, indent=2)
        print(f"  ✓ Splash events saved to {json_path} ({len(events)} events)")

        # ── Save debug PNG ────────────────────────────────────────────────────
        png_path = ctx.output_dir / f"{stem}_splash_debug.png"

        energy = compute_energy_envelope(
            waveform, hop_length=self.hop_length, smooth_window=self.smooth_window
        )
        onset = compute_onset_envelope(
            waveform, sr=sr, hop_length=self.hop_length, smooth_window=self.smooth_window
        )
        n_frames = min(len(energy), len(onset))
        energy = energy[:n_frames]
        onset = onset[:n_frames]
        times = np.arange(n_frames) * self.hop_length / sr

        fig, axes = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

        axes[0].plot(times, energy, color="steelblue", linewidth=0.8, label="RMS energy")
        axes[0].set_ylabel("RMS Energy")
        axes[0].legend(loc="upper right", fontsize=8)

        axes[1].plot(times, onset, color="darkorange", linewidth=0.8, label="Onset strength")
        axes[1].set_ylabel("Onset Strength")
        axes[1].set_xlabel("Time (s)")
        axes[1].legend(loc="upper right", fontsize=8)

        for ev in events:
            axes[0].axvline(x=ev.time_sec, color="red", linewidth=0.8, alpha=0.7)
            axes[1].axvline(x=ev.time_sec, color="red", linewidth=0.8, alpha=0.7)

        fig.suptitle(
            f"{stem} – splash detection ({len(events)} events)", fontsize=11
        )
        fig.tight_layout()
        fig.savefig(png_path, dpi=150)
        plt.close(fig)

        print(f"  ✓ Splash debug image saved to {png_path}")

        ctx.artifacts.splash_events_json = json_path
        ctx.artifacts.splash_debug_png = png_path
        ctx.extra["splash_events_path"] = json_path  # backward compat
        ctx.extra["splash_debug_path"] = png_path
        return ctx


def _register_builtins() -> None:
    StepRegistry.register("analyze", AnalyzeStep)
    StepRegistry.register("normalize", NormalizeStep)
    StepRegistry.register("band_split", BandSplitStep)
    StepRegistry.register("grain", GrainStep)
    StepRegistry.register("ensure_metadata", EnsureMetadataStep)
    StepRegistry.register("splash", SplashStep)


_register_builtins()
