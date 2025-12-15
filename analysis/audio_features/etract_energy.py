import librosa
import numpy as np


def extract_rms_energy(
    waveform: np.ndarray,
    hop_length: int = 512
) -> np.ndarray:
    """
    音声波形から全体エネルギー包絡（RMS）を抽出する

    Parameters
    ----------
    waveform : np.ndarray
        モノラル音声の時間波形
    hop_length : int
        フレーム間隔（サンプル数）

    Returns
    -------
    np.ndarray
        各フレームにおける RMS エネルギー
    """

    rms_energy = librosa.feature.rms(
        y=waveform,
        hop_length=hop_length
    )[0]

    return rms_energy
