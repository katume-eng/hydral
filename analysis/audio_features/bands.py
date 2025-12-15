import librosa
import numpy as np

def extract_bands(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512
) -> dict:
    """
    周波数帯域ごとのエネルギー
    """
    stft = librosa.stft(y, hop_length=hop_length)
    mag = np.abs(stft)

    freqs = librosa.fft_frequencies(sr=sr)

    def band_energy(low, high):
        idx = (freqs >= low) & (freqs < high)
        return mag[idx].mean(axis=0)

    return {
        "low": band_energy(20, 200),
        "mid": band_energy(200, 2000),
        "high": band_energy(2000, 8000),
    }
