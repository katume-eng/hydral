# processing/assemble.py
from __future__ import annotations

from typing import Iterable, List, Optional, Sequence
from pydub import AudioSegment


def concat(grains: Sequence[AudioSegment]) -> AudioSegment:
    """
    単純連結（クロスフェード無し）。
    """
    if not grains:
        return AudioSegment.silent(duration=0)
    out = grains[0]
    for g in grains[1:]:
        out += g
    return out


def concat_crossfade(
    grains: Sequence[AudioSegment],
    *,
    crossfade_ms: int = 10
) -> AudioSegment:
    """
    クロスフェード付き連結。クリックノイズ対策として有効。
    """
    if not grains:
        return AudioSegment.silent(duration=0)
    if crossfade_ms <= 0:
        return concat(grains)

    out = grains[0]
    for g in grains[1:]:
        cf = min(crossfade_ms, len(out), len(g))
        out = out.append(g, crossfade=cf)
    return out


def mixdown(
    tracks: Sequence[AudioSegment],
    *,
    headroom_db: float = 1.0
) -> AudioSegment:
    """
    複数トラックを重ねてミックスダウンする。
    headroom_db 分だけ全体を下げ、クリップしにくくする。
    """
    if not tracks:
        return AudioSegment.silent(duration=0)
    out = tracks[0]
    for t in tracks[1:]:
        out = out.overlay(t)
    if headroom_db > 0:
        out = out - headroom_db
    return out


def safe_normalize(
    audio: AudioSegment,
    *,
    target_dbfs: float = -1.0,
    max_gain_db: float = 24.0
) -> AudioSegment:
    """
    クリップ回避のための安全な正規化（dBFS基準）。
    無音に近い場合はそのまま返す。
    """
    # dBFS が -inf の場合（完全無音）
    if audio.dBFS == float("-inf"):
        return audio

    gain = target_dbfs - audio.dBFS
    gain = max(-max_gain_db, min(max_gain_db, gain))
    return audio.apply_gain(gain)
