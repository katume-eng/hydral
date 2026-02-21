from pathlib import Path
import numpy as np
import librosa


def load_audio_waveform(
    wav_path: str | Path,
    *,
    mono: bool = True,
    target_sample_rate: int | None = None
) -> tuple[np.ndarray, int]:
    """
    WAV ファイルを読み込み、解析用の波形データとサンプリングレートを返す

    Parameters
    ----------
    wav_path : str | Path
        入力 WAV ファイルのパス
    mono : bool, optional
        モノラルに変換するかどうか（解析用途では通常 True）
    target_sample_rate : int | None, optional
        リサンプリング後のサンプリングレート。
        None の場合は元のサンプリングレートを保持する。

    Returns
    -------
    waveform : np.ndarray
        音声の時間波形（1次元配列）
    sample_rate : int
        サンプリングレート（Hz）
    """

    wav_path = Path(wav_path)

    if not wav_path.exists():
        raise FileNotFoundError(f"WAV file not found: {wav_path}")

    waveform, sample_rate = librosa.load(
        wav_path,
        sr=target_sample_rate,
        mono=mono
    )

    return waveform, sample_rate
