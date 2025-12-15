import librosa
import numpy as np

def extract_energy(
    y: np.ndarray,
    hop_length: int = 512
) -> np.ndarray:
    """
    音全体のエネルギー包絡（RMS）
    """
    rms = librosa.feature.rms(
        y=y,
        hop_length=hop_length
    )[0]
    return rms
