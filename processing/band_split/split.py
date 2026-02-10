"""
Core logic for band splitting and tonal/noise separation.

This module splits audio into 5 frequency bands and further separates
each band into tonal and noise components using HPSS.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import librosa
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt


# Default band definitions (Hz)
DEFAULT_BANDS = {
    "band01": {"low_hz": 20, "high_hz": 120},
    "band02": {"low_hz": 120, "high_hz": 300},
    "band03": {"low_hz": 300, "high_hz": 900},
    "band04": {"low_hz": 900, "high_hz": 3000},
    "band05": {"low_hz": 3000, "high_hz": 12000},
}


def compute_sha256(filepath: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def bandpass_filter(
    audio: np.ndarray,
    low_hz: float,
    high_hz: float,
    sr: int,
    order: int = 5
) -> np.ndarray:
    """
    Apply Butterworth bandpass filter to audio.
    
    Args:
        audio: Input audio array (mono or multi-channel)
        low_hz: Lower frequency bound
        high_hz: Upper frequency bound
        sr: Sample rate
        order: Filter order
        
    Returns:
        Filtered audio array
    """
    nyquist = sr / 2.0
    
    # Clip frequencies to valid range
    low_hz = max(1.0, min(low_hz, nyquist - 1))
    high_hz = max(low_hz + 1, min(high_hz, nyquist - 1))
    
    # Design Butterworth bandpass filter
    sos = butter(order, [low_hz, high_hz], btype='band', fs=sr, output='sos')
    
    # Apply filter (handles multi-channel)
    if audio.ndim == 1:
        filtered = sosfiltfilt(sos, audio)
    else:
        # Apply to each channel separately
        filtered = np.array([sosfiltfilt(sos, audio[ch]) for ch in range(audio.shape[0])])
    
    return filtered


def separate_tonal_noise(
    audio: np.ndarray,
    sr: int,
    kernel_size: int = 31,
    margin: float = 2.0
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Separate audio into tonal (harmonic) and noise (percussive) components.
    
    Uses librosa's HPSS (Harmonic-Percussive Source Separation).
    
    Args:
        audio: Input audio array (mono or multi-channel)
        sr: Sample rate
        kernel_size: Size of the median filter kernel
        margin: Margin for soft masking
        
    Returns:
        Tuple of (tonal, noise) audio arrays
    """
    if audio.ndim == 1:
        # Mono audio
        tonal, noise = librosa.effects.hpss(
            audio,
            kernel_size=kernel_size,
            margin=margin
        )
    else:
        # Multi-channel: process each channel
        tonal_channels = []
        noise_channels = []
        for ch in range(audio.shape[0]):
            t, n = librosa.effects.hpss(
                audio[ch],
                kernel_size=kernel_size,
                margin=margin
            )
            tonal_channels.append(t)
            noise_channels.append(n)
        tonal = np.array(tonal_channels)
        noise = np.array(noise_channels)
    
    return tonal, noise


def normalize_peak(audio: np.ndarray, target_db: float = -1.0) -> np.ndarray:
    """
    Normalize audio to target peak level in dB.
    
    Args:
        audio: Input audio array
        target_db: Target peak level in dB (e.g., -1.0 for -1 dBFS)
        
    Returns:
        Normalized audio array
    """
    peak = np.abs(audio).max()
    if peak > 0:
        target_linear = 10 ** (target_db / 20.0)
        audio = audio * (target_linear / peak)
    return audio


def compute_rms(audio: np.ndarray) -> float:
    """
    Compute RMS (Root Mean Square) value of audio.
    
    For multi-channel audio, computes RMS across all channels combined,
    providing a single overall power measurement.
    
    Args:
        audio: Input audio array (mono or multi-channel)
        
    Returns:
        RMS value as a float
    """
    return float(np.sqrt(np.mean(audio ** 2)))


def split_into_bands(
    input_path: Path,
    output_dir: Path,
    bands: Optional[Dict] = None,
    target_sr: Optional[int] = None,
    mono: bool = False,
    filter_order: int = 5,
    hpss_kernel_size: int = 31,
    hpss_margin: float = 2.0,
) -> Dict:
    """
    Main function to split audio into frequency bands and tonal/noise components.
    
    Args:
        input_path: Path to input WAV file
        output_dir: Directory for output files
        bands: Custom band definitions (optional, uses DEFAULT_BANDS if None)
        target_sr: Target sample rate for processing (None = use original)
        mono: Convert to mono before processing
        filter_order: Butterworth filter order
        hpss_kernel_size: Kernel size for HPSS
        hpss_margin: Margin for HPSS soft masking
        
    Returns:
        Manifest dictionary with processing metadata
    """
    # Use default bands if not specified
    if bands is None:
        bands = DEFAULT_BANDS
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load audio
    audio, sr = librosa.load(input_path, sr=target_sr, mono=mono)
    
    # Ensure audio is in the right shape (channels, samples)
    if audio.ndim == 1:
        # Mono audio: shape = (samples,)
        # Keep as is for processing
        original_shape = "mono"
        channels = 1
    else:
        # Multi-channel: shape = (channels, samples)
        original_shape = "multi"
        channels = audio.shape[0]
    
    # Get input file info
    input_info = sf.info(str(input_path))
    duration_sec = len(audio) / sr if audio.ndim == 1 else audio.shape[1] / sr
    
    # Compute SHA256 of input
    sha256 = compute_sha256(input_path)
    
    # Initialize manifest
    manifest = {
        "version": "v1",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "input": {
            "path": str(input_path),
            "sample_rate": sr,
            "channels": channels,
            "duration_sec": float(duration_sec),
            "sha256": sha256,
        },
        "processing": {
            "band_method": "butter_bandpass_sosfiltfilt",
            "band_params": {
                "order": filter_order,
            },
            "hpss_method": "librosa_hpss",
            "hpss_params": {
                "kernel_size": hpss_kernel_size,
                "margin": hpss_margin,
            },
        },
        "bands": bands,
        "outputs": [],
    }
    
    # Process each band
    for band_id, band_spec in sorted(bands.items()):
        low_hz = band_spec["low_hz"]
        high_hz = band_spec["high_hz"]
        
        # Apply bandpass filter
        band_audio = bandpass_filter(audio, low_hz, high_hz, sr, order=filter_order)
        
        # Separate into tonal and noise
        tonal, noise = separate_tonal_noise(
            band_audio,
            sr,
            kernel_size=hpss_kernel_size,
            margin=hpss_margin
        )
        
        # Normalize to avoid clipping
        tonal = normalize_peak(tonal, target_db=-1.0)
        noise = normalize_peak(noise, target_db=-1.0)
        
        # Write outputs
        for component, comp_audio in [("tonal", tonal), ("noise", noise)]:
            output_filename = f"{band_id}_{component}.wav"
            output_path = output_dir / output_filename
            
            # Transpose if multi-channel (soundfile expects shape: samples, channels)
            if comp_audio.ndim > 1:
                comp_audio_write = comp_audio.T
            else:
                comp_audio_write = comp_audio
            
            # Write as float32 WAV
            sf.write(
                str(output_path),
                comp_audio_write,
                sr,
                subtype='FLOAT'
            )
            
            # Compute RMS for this output
            rms_value = compute_rms(comp_audio)
            
            # Add to manifest
            comp_duration = len(comp_audio) / sr if comp_audio.ndim == 1 else comp_audio.shape[1] / sr
            manifest["outputs"].append({
                "path": output_filename,
                "band_id": band_id,
                "component": component,
                "sample_rate": sr,
                "channels": channels,
                "duration_sec": float(comp_duration),
                "format": "float32",
                "rms_average": rms_value,
            })
    
    # Write manifest JSON
    manifest_path = output_dir / "split_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    return manifest
