"""
Band Split Module

Splits audio into frequency bands and separates each band into
tonal (harmonic) and noise (percussive) components.
"""

from .split import (
    DEFAULT_BANDS,
    bandpass_filter,
    compute_rms,
    normalize_peak,
    separate_tonal_noise,
    split_into_bands,
)

__all__ = [
    "DEFAULT_BANDS",
    "bandpass_filter",
    "compute_rms",
    "normalize_peak",
    "separate_tonal_noise",
    "split_into_bands",
]
