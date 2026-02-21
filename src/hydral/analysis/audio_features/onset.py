import librosa
import numpy as np


def extract_onset_strength(
    waveform: np.ndarray,
    sample_rate: int,
    hop_length: int = 512
) -> np.ndarray:
    """
    音声からオンセット強度（時間方向のイベント感）を抽出する

    Parameters
    ----------
    waveform : np.ndarray
        モノラル音声の時間波形
    sample_rate : int
        サンプリングレート（Hz）
    hop_length : int
        フレーム間隔（サンプル数）

    Returns
    -------
    np.ndarray
        各フレームにおけるオンセット強度
    """

    onset_strength_envelope = librosa.onset.onset_strength(
        y=waveform,
        sr=sample_rate,
        hop_length=hop_length
    )

    return onset_strength_envelope
