"""Splash event detection for water sound recordings.

Detects instantaneous splash/impact events (バシャッ, ポチャン) in a
mono audio waveform, while remaining relatively quiet on sustained sounds
like continuous river or rain.

Usage
-----
>>> from hydral.analysis.events.splash import detect_splash_events
>>> events = detect_splash_events(y, sr)
>>> for ev in events:
...     print(ev.time_sec, ev.strength)
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from hydral.analysis.audio_features.etract_energy import extract_rms_energy
from hydral.analysis.audio_features.onset import extract_onset_strength
from hydral.analysis.audio_features.smoothing import apply_moving_average


# ── Data model ────────────────────────────────────────────────────────────────


@dataclass
class SplashEvent:
    """A single detected splash event.

    Attributes
    ----------
    time_sec : float
        Event time in seconds (= sample_index / sr).
    strength : float
        Combined energy × onset score at the event peak.
    sample_index : int
        Waveform sample index corresponding to the event.
    """

    time_sec: float
    strength: float
    sample_index: int


# ── JSON helpers ──────────────────────────────────────────────────────────────


def to_dict(event: SplashEvent) -> dict[str, float | int]:
    """Convert a SplashEvent to a JSON-serialisable dict."""
    return {
        "time_sec": event.time_sec,
        "strength": event.strength,
        "sample_index": event.sample_index,
    }


def events_to_dicts(events: list[SplashEvent]) -> list[dict[str, float | int]]:
    """Convert a list of SplashEvents to a list of dicts."""
    return [to_dict(e) for e in events]


# ── Internal helpers ──────────────────────────────────────────────────────────


def compute_energy_envelope(
    y: np.ndarray,
    hop_length: int,
    smooth_window: int,
) -> np.ndarray:
    """Return a smoothed RMS energy envelope.

    Parameters
    ----------
    y : np.ndarray
        Mono audio waveform.
    hop_length : int
        Hop size in samples between analysis frames.
    smooth_window : int
        Moving-average window size (frames).  Set to 1 to disable.

    Returns
    -------
    np.ndarray
        Smoothed RMS energy per frame.
    """
    energy = extract_rms_energy(y, hop_length=hop_length)
    if smooth_window > 1:
        energy = apply_moving_average(energy, window_size=smooth_window)
    return energy


def compute_onset_envelope(
    y: np.ndarray,
    sr: int,
    hop_length: int,
    smooth_window: int,
) -> np.ndarray:
    """Return a lightly smoothed onset-strength envelope.

    A light smooth (window=3) reduces frame-to-frame noise while keeping
    the transient peak sharp enough for splash detection.

    Parameters
    ----------
    y : np.ndarray
        Mono audio waveform.
    sr : int
        Sample rate in Hz.
    hop_length : int
        Hop size in samples between analysis frames.
    smooth_window : int
        Moving-average window size (frames).  Set to 1 to disable.

    Returns
    -------
    np.ndarray
        Smoothed onset-strength per frame.
    """
    onset = extract_onset_strength(y, sr, hop_length=hop_length)
    if smooth_window > 1:
        # Keep onset sharp: cap the smooth window at 3 even if caller
        # requests more, so transient peaks are not flattened.
        onset = apply_moving_average(onset, window_size=min(smooth_window, 3))
    return onset


def pick_event_peaks(
    combined: np.ndarray,
    energy: np.ndarray,
    onset: np.ndarray,
    energy_threshold_std: float,
    onset_threshold_std: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Return frame indices and scores of candidate splash peaks.

    Candidates must be:
    1. A local maximum in the combined score (immediate neighbours are lower).
    2. Above the adaptive energy threshold (mean + k·std).
    3. Above the adaptive onset threshold (mean + k·std).

    Requiring *both* high energy and high onset keeps sustained sounds (river,
    rain) from triggering – they typically have elevated energy but low onset.

    Parameters
    ----------
    combined : np.ndarray
        Frame-wise product of normalised energy × onset (or similar).
    energy : np.ndarray
        RMS energy per frame.
    onset : np.ndarray
        Onset strength per frame.
    energy_threshold_std : float
        Number of standard deviations above the mean for the energy gate.
    onset_threshold_std : float
        Number of standard deviations above the mean for the onset gate.

    Returns
    -------
    peak_frames : np.ndarray of int
        Frame indices of accepted peaks.
    peak_scores : np.ndarray of float
        Combined scores at those frames.
    """
    n = len(combined)
    if n < 3:
        return np.array([], dtype=int), np.array([], dtype=float)

    # Adaptive thresholds
    energy_thresh = float(np.mean(energy) + energy_threshold_std * np.std(energy))
    onset_thresh = float(np.mean(onset) + onset_threshold_std * np.std(onset))

    peak_frames: list[int] = []
    peak_scores: list[float] = []

    for i in range(1, n - 1):
        # Local maximum check (strict on both sides)
        if combined[i] <= combined[i - 1] or combined[i] <= combined[i + 1]:
            continue
        # Both energy and onset must cross their respective thresholds
        if energy[i] < energy_thresh:
            continue
        if onset[i] < onset_thresh:
            continue
        peak_frames.append(i)
        peak_scores.append(float(combined[i]))

    return np.array(peak_frames, dtype=int), np.array(peak_scores, dtype=float)


def merge_close_events(
    peak_frames: np.ndarray,
    peak_scores: np.ndarray,
    sr: int,
    hop_length: int,
    min_interval_sec: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Remove peaks that are too close together, keeping the strongest.

    Events within *min_interval_sec* of an already-accepted event are
    suppressed (refractory period logic).

    Parameters
    ----------
    peak_frames : np.ndarray of int
        Frame indices of candidate peaks (must be sorted ascending).
    peak_scores : np.ndarray of float
        Combined scores at those frames.
    sr : int
        Sample rate in Hz.
    hop_length : int
        Hop size in samples.
    min_interval_sec : float
        Minimum allowed gap between events in seconds.

    Returns
    -------
    kept_frames : np.ndarray of int
    kept_scores : np.ndarray of float
    """
    if len(peak_frames) == 0:
        return peak_frames, peak_scores

    min_interval_frames = min_interval_sec * sr / hop_length

    kept_frames: list[int] = []
    kept_scores: list[float] = []
    last_kept_frame: float = -min_interval_frames - 1  # sentinel

    for frame, score in zip(peak_frames, peak_scores):
        if frame - last_kept_frame >= min_interval_frames:
            kept_frames.append(int(frame))
            kept_scores.append(float(score))
            last_kept_frame = frame

    return np.array(kept_frames, dtype=int), np.array(kept_scores, dtype=float)


# ── Public API ────────────────────────────────────────────────────────────────


def detect_splash_events(
    y: np.ndarray,
    sr: int,
    *,
    frame_length: int = 1024,
    hop_length: int = 256,
    smooth_window: int = 5,
    energy_threshold_std: float = 2.0,
    onset_threshold_std: float = 1.5,
    min_interval_sec: float = 0.12,
) -> list[SplashEvent]:
    """Detect splash events in a mono audio waveform.

    Splash events are transient, high-energy impacts (e.g. バシャッ, ポチャン)
    as opposed to sustained water sounds like river flow or rain.

    Parameters
    ----------
    y : np.ndarray
        Mono float32/float64 audio waveform.
    sr : int
        Sample rate in Hz.
    frame_length : int
        FFT window length in samples (used implicitly via hop_length).
    hop_length : int
        Hop size between analysis frames in samples.
    smooth_window : int
        Window size for moving-average smoothing of the energy envelope.
    energy_threshold_std : float
        Energy gate: mean + energy_threshold_std × σ.  Higher = fewer events.
    onset_threshold_std : float
        Onset gate: mean + onset_threshold_std × σ.  Higher = fewer events.
    min_interval_sec : float
        Refractory period.  Events closer than this are merged (strongest kept).

    Returns
    -------
    list[SplashEvent]
        Time-ordered list of detected splash events.  May be empty.
    """
    if y is None or len(y) == 0:
        return []

    # Require at least 2 full analysis frames worth of audio.
    if len(y) < 2 * hop_length:
        return []

    # ── 1. Feature extraction ────────────────────────────────────────────────
    energy = compute_energy_envelope(y, hop_length=hop_length, smooth_window=smooth_window)
    onset = compute_onset_envelope(y, sr=sr, hop_length=hop_length, smooth_window=smooth_window)

    # Align lengths (librosa may differ by 1 frame between the two)
    n_frames = min(len(energy), len(onset))
    energy = energy[:n_frames]
    onset = onset[:n_frames]

    if n_frames < 3:
        return []

    # ── 2. Combined score (energy × onset product, normalised to [0, 1]) ─────
    # Normalise each to [0, 1] so neither dominates by scale.
    e_max = float(np.max(energy))
    o_max = float(np.max(onset))
    energy_norm = energy / e_max if e_max > 0 else energy
    onset_norm = onset / o_max if o_max > 0 else onset
    combined = energy_norm * onset_norm

    # ── 3. Pick local-maximum peaks that pass both thresholds ────────────────
    peak_frames, peak_scores = pick_event_peaks(
        combined,
        energy=energy,
        onset=onset,
        energy_threshold_std=energy_threshold_std,
        onset_threshold_std=onset_threshold_std,
    )

    if len(peak_frames) == 0:
        return []

    # ── 4. Refractory period: drop peaks that are too close together ─────────
    peak_frames, peak_scores = merge_close_events(
        peak_frames,
        peak_scores,
        sr=sr,
        hop_length=hop_length,
        min_interval_sec=min_interval_sec,
    )

    # ── 5. Build result list ─────────────────────────────────────────────────
    events: list[SplashEvent] = []
    for frame, score in zip(peak_frames, peak_scores):
        sample_idx = int(frame) * hop_length
        time_sec = sample_idx / sr
        events.append(SplashEvent(time_sec=time_sec, strength=score, sample_index=sample_idx))

    return events
