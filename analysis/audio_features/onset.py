import librosa
import numpy as np

def extract_onset(
    y: np.ndarray,
    sr: int,
    hop_length: int = 512
) -> np.ndarray:
    """
    オンセット強度（イベント感）
    """
    onset_env = librosa.onset.onset_strength(
        y=y,
        sr=sr,
        hop_length=hop_length
    )
    return onset_env
