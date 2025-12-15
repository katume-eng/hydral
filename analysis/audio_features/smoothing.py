import numpy as np

def moving_average(
    x: np.ndarray,
    window: int = 5
) -> np.ndarray:
    """
    移動平均による平滑化
    """
    if window <= 1:
        return x

    kernel = np.ones(window) / window
    return np.convolve(x, kernel, mode="same")
