import numpy as np


def apply_moving_average(
    signal: np.ndarray,
    window_size: int = 5
) -> np.ndarray:
    """
    移動平均フィルタによって信号を平滑化する

    Parameters
    ----------
    signal : np.ndarray
        入力信号（1次元配列）
    window_size : int
        平滑化に用いる窓幅（フレーム数）

    Returns
    -------
    np.ndarray
        平滑化後の信号
    """

    if window_size <= 1:
        return signal

    averaging_kernel = np.ones(window_size) / window_size

    smoothed_signal = np.convolve(
        signal,
        averaging_kernel,
        mode="same"
    )

    return smoothed_signal
