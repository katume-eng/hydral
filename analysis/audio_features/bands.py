import librosa
import numpy as np


def extract_frequency_band_energies(
    waveform: np.ndarray,
    sample_rate: int,
    hop_length: int = 512
) -> dict[str, np.ndarray]:
    """
    音声波形から周波数帯域ごとのエネルギー時系列を抽出する

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
    dict[str, np.ndarray]
        low / mid / high 各帯域のエネルギー配列
    """

    # 短時間フーリエ変換（時間 × 周波数）
    stft_complex = librosa.stft(
        waveform,
        hop_length=hop_length
    )

    # 振幅スペクトル
    magnitude_spectrogram = np.abs(stft_complex)

    # 各周波数ビンに対応する周波数（Hz）
    frequency_bins_hz = librosa.fft_frequencies(
        sr=sample_rate
    )

    def compute_band_energy(
        low_frequency_hz: float,
        high_frequency_hz: float
    ) -> np.ndarray:
        """
        指定した周波数帯域の平均エネルギーを計算
        """
        band_mask = (
            (frequency_bins_hz >= low_frequency_hz) &
            (frequency_bins_hz < high_frequency_hz)
        )

        band_magnitudes = magnitude_spectrogram[band_mask]

        # 周波数方向に平均 → 時間方向の配列
        return band_magnitudes.mean(axis=0)

    return {
        "low": compute_band_energy(20.0, 200.0),
        "mid": compute_band_energy(200.0, 2000.0),
        "high": compute_band_energy(2000.0, 8000.0),
    }
