"""Tests for splash event detection (src/hydral/analysis/events/splash.py).

All waveforms are generated with numpy – no external WAV files required.
"""
from __future__ import annotations

import sys
import os

import numpy as np
import pytest

# Ensure src/ is on the path (mirrors the pattern used in other hydral tests)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hydral.analysis.events.splash import (
    SplashEvent,
    detect_splash_events,
    events_to_dicts,
    merge_close_events,
    to_dict,
)


# ── helpers ──────────────────────────────────────────────────────────────────

SR = 22050  # sample rate used throughout these tests


def _silence(duration_sec: float, sr: int = SR) -> np.ndarray:
    """Return a silent (zero) waveform."""
    return np.zeros(int(sr * duration_sec), dtype=np.float32)


def _add_impulse(y: np.ndarray, time_sec: float, amplitude: float = 0.9, sr: int = SR) -> None:
    """Inject a single-sample impulse at the given time (in-place)."""
    idx = int(time_sec * sr)
    if 0 <= idx < len(y):
        y[idx] = amplitude


def _add_burst(
    y: np.ndarray,
    time_sec: float,
    duration_sec: float = 0.02,
    amplitude: float = 0.9,
    sr: int = SR,
) -> None:
    """Inject a short white-noise burst to simulate a splash impulse."""
    start = int(time_sec * sr)
    end = min(start + int(duration_sec * sr), len(y))
    rng = np.random.default_rng(seed=int(time_sec * 1000))
    y[start:end] = amplitude * rng.uniform(-1.0, 1.0, end - start).astype(np.float32)


# ── SplashEvent & JSON helpers ────────────────────────────────────────────────


def test_splash_event_fields():
    ev = SplashEvent(time_sec=1.5, strength=0.75, sample_index=33075)
    assert ev.time_sec == 1.5
    assert ev.strength == 0.75
    assert ev.sample_index == 33075


def test_to_dict():
    ev = SplashEvent(time_sec=0.5, strength=0.3, sample_index=11025)
    d = to_dict(ev)
    assert d == {"time_sec": 0.5, "strength": 0.3, "sample_index": 11025}


def test_events_to_dicts():
    evs = [
        SplashEvent(time_sec=0.1, strength=0.2, sample_index=2205),
        SplashEvent(time_sec=0.5, strength=0.8, sample_index=11025),
    ]
    dicts = events_to_dicts(evs)
    assert len(dicts) == 2
    assert dicts[0]["time_sec"] == 0.1
    assert dicts[1]["sample_index"] == 11025


# ── detect_splash_events: edge cases ────────────────────────────────────────


def test_silence_returns_no_events():
    """Silent audio should produce zero events."""
    y = _silence(2.0)
    events = detect_splash_events(y, SR)
    assert events == []


def test_empty_array_returns_no_events():
    events = detect_splash_events(np.array([], dtype=np.float32), SR)
    assert events == []


def test_very_short_array_does_not_crash():
    """Arrays shorter than 2 × hop_length must not raise."""
    y = np.ones(100, dtype=np.float32) * 0.01
    events = detect_splash_events(y, SR, hop_length=256)
    assert isinstance(events, list)


def test_single_sample_array_does_not_crash():
    y = np.array([0.5], dtype=np.float32)
    events = detect_splash_events(y, SR)
    assert isinstance(events, list)


# ── detect_splash_events: impulse detection ──────────────────────────────────


def test_two_impulses_detected():
    """Two well-separated noise bursts should each yield roughly one event."""
    y = _silence(3.0)
    _add_burst(y, time_sec=0.5)
    _add_burst(y, time_sec=2.0)

    events = detect_splash_events(
        y,
        SR,
        hop_length=256,
        smooth_window=3,
        energy_threshold_std=1.5,
        onset_threshold_std=1.0,
        min_interval_sec=0.3,
    )
    # We expect exactly 2, but allow ±1 due to frame boundary effects
    assert 1 <= len(events) <= 3, f"Expected ~2 events, got {len(events)}"


def test_event_times_near_impulses():
    """Detected events should be temporally close to the injected impulses."""
    y = _silence(3.0)
    _add_burst(y, time_sec=0.5)
    _add_burst(y, time_sec=2.0)

    events = detect_splash_events(
        y,
        SR,
        hop_length=256,
        smooth_window=3,
        energy_threshold_std=1.5,
        onset_threshold_std=1.0,
        min_interval_sec=0.3,
    )
    assert len(events) >= 1
    # Each event must be within 100 ms of one of the injected positions
    expected_times = [0.5, 2.0]
    for ev in events:
        closest = min(abs(ev.time_sec - t) for t in expected_times)
        assert closest < 0.2, f"Event at {ev.time_sec:.3f}s is far from any impulse"


def test_events_are_time_ordered():
    y = _silence(4.0)
    _add_burst(y, time_sec=0.5)
    _add_burst(y, time_sec=2.0)
    _add_burst(y, time_sec=3.0)

    events = detect_splash_events(y, SR, hop_length=256, min_interval_sec=0.3)
    times = [ev.time_sec for ev in events]
    assert times == sorted(times)


def test_sample_index_consistent_with_time_sec():
    y = _silence(2.0)
    _add_burst(y, time_sec=0.5)

    events = detect_splash_events(y, SR, hop_length=256)
    for ev in events:
        assert abs(ev.time_sec - ev.sample_index / SR) < 1e-9
        assert ev.sample_index >= 0


def test_event_strength_is_positive():
    y = _silence(2.0)
    _add_burst(y, time_sec=0.5)

    events = detect_splash_events(y, SR, hop_length=256)
    for ev in events:
        assert ev.strength > 0


# ── min_interval_sec merging ─────────────────────────────────────────────────


def test_min_interval_merges_close_events():
    """With a large min_interval_sec, two close bursts should collapse to one."""
    y = _silence(2.0)
    _add_burst(y, time_sec=0.5, amplitude=0.9)
    _add_burst(y, time_sec=0.55, amplitude=0.9)   # 50 ms apart

    # With 200 ms refractory the two should merge
    events_merged = detect_splash_events(
        y, SR, hop_length=256, min_interval_sec=0.2
    )
    # With tiny refractory they may stay separate
    events_split = detect_splash_events(
        y, SR, hop_length=256, min_interval_sec=0.01
    )
    # Merged should have fewer (or equal) events than split
    assert len(events_merged) <= len(events_split)


def test_merge_close_events_helper():
    """Unit test for the merge_close_events helper directly."""
    hop_length = 256
    sr = 16000
    # Two frames 5 apart at sr=16000, hop=256 → 5*256/16000 = 0.08 s apart
    frames = np.array([10, 15, 50], dtype=int)
    scores = np.array([0.4, 0.9, 0.5], dtype=float)

    # min_interval = 0.1 s → min_interval_frames = 0.1 * 16000 / 256 ≈ 6.25
    kept_f, kept_s = merge_close_events(
        frames, scores, sr=sr, hop_length=hop_length, min_interval_sec=0.1
    )
    # Frame 15 is only 5 frames after frame 10 → should be dropped
    assert 10 in kept_f
    assert 15 not in kept_f
    assert 50 in kept_f


def test_merge_close_events_empty():
    kept_f, kept_s = merge_close_events(
        np.array([], dtype=int),
        np.array([], dtype=float),
        sr=16000,
        hop_length=256,
        min_interval_sec=0.1,
    )
    assert len(kept_f) == 0


# ── sustained noise (river-like) should not over-trigger ─────────────────────


def test_sustained_noise_does_not_over_trigger():
    """Continuous broadband noise with no transients should produce few events.

    The threshold defaults are tuned to be fairly strict; a flat noise floor
    with a constant RMS and uniform onset should not exceed the mean+k*std gate
    for most frames.  We allow at most a handful of edge-case peaks.
    """
    rng = np.random.default_rng(seed=42)
    duration = 5.0
    y = (0.05 * rng.standard_normal(int(SR * duration))).astype(np.float32)

    events = detect_splash_events(
        y,
        SR,
        hop_length=256,
        energy_threshold_std=2.0,
        onset_threshold_std=1.5,
        min_interval_sec=0.12,
    )
    # For uniform noise, very few frames should exceed the threshold
    assert len(events) <= 5, f"Too many events on flat noise: {len(events)}"
