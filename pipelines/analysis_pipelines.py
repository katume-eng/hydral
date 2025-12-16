from pathlib import Path
from typing import Dict

import numpy as np

from analysis.audio_features.io import load_audio_waveform
from analysis.audio_features.etract_energy import extract_rms_energy
from analysis.audio_features.bands import extract_frequency_band_energies
from analysis.audio_features.onset import extract_onset_strength
from analysis.audio_features.smoothing import apply_moving_average
from routes import PATH


def run_audio_analysis_pipeline(
    wav_path: str | Path,
    *,
    hop_length: int = 512,
    smoothing_window: int = 5,
    sample_rate: int | None = None
) -> Dict[str, np.ndarray]:
    """
    音声ファイルを解析し、可視化・表現向けの数値特徴量を生成する

    Parameters
    ----------
    wav_path : str | Path
        入力 WAV ファイル
    hop_length : int
        解析フレーム間隔（全特徴量で統一）
    smoothing_window : int
        平滑化に用いる窓幅
    sample_rate : int | None
        リサンプリング後のサンプリングレート（None なら元のまま）

    Returns
    -------
    Dict[str, np.ndarray]
        解析結果（時系列配列）
    """

    # --- 1. WAV → 波形 ---
    waveform, sr = load_audio_waveform(
        wav_path,
        target_sample_rate=sample_rate
    )

    # --- 2. 特徴量抽出 ---
    rms_energy = extract_rms_energy(
        waveform,
        hop_length=hop_length
    )

    band_energies = extract_frequency_band_energies(
        waveform,
        sr,
        hop_length=hop_length
    )

    onset_strength = extract_onset_strength(
        waveform,
        sr,
        hop_length=hop_length
    )

    # --- 3. 平滑化（制御信号向け） ---
    rms_energy = apply_moving_average(
        rms_energy,
        window_size=smoothing_window
    )

    for band_name in band_energies:
        band_energies[band_name] = apply_moving_average(
            band_energies[band_name],
            window_size=smoothing_window
        )

    # onset はイベント用途なので弱め or 無し
    onset_strength = apply_moving_average(
        onset_strength,
        window_size=3
    )

    # --- 4. 結果をまとめる ---
    features = {
        "rms": rms_energy,
        "low": band_energies["low"],
        "mid": band_energies["mid"],
        "high": band_energies["high"],
        "onset": onset_strength,
        "meta": {
            "sample_rate": sr,
            "hop_length": hop_length,
            "num_frames": len(rms_energy),
        },
    }

    return features

import json

if __name__ == "__main__":
    features = run_audio_analysis_pipeline(
        wav_path=PATH["input_wav"]
    )

    out_dir = Path(PATH["analysis_outputs"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # numpy → list に変換して保存
    serializable = {
        k: v.tolist() if isinstance(v, np.ndarray) else v
        for k, v in features.items()
    }

    with open(out_dir / "audio_features.json", "w") as f:
        json.dump(serializable, f, indent=2)
