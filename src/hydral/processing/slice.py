# processing/slice.py
from __future__ import annotations

import random
from typing import List, Optional
from pydub import AudioSegment


def slice_grains(
    audio: AudioSegment,
    *,
    grain_ms: int = 80,
    hop_ms: Optional[int] = None,
    start_ms: int = 0,
    end_ms: Optional[int] = None,
    jitter_ms: int = 0,
    pad_end: bool = False,
    fade_ms: int = 5,
    seed: Optional[int] = None,
) -> List[AudioSegment]:
    """
    AudioSegment をグレイン列にスライスする。

    - grain_ms: グレイン長（ms）
    - hop_ms: ステップ（ms）。None の場合 grain_ms と同じ（非オーバーラップ）
    - jitter_ms: 各グレイン開始位置を ±jitter_ms だけ揺らす
    - pad_end: 末尾で足りない分を無音でパディングして一定長にする
    - fade_ms: クリック対策のフェードイン/アウト
    """
    if grain_ms <= 0:
        return []
    if hop_ms is None:
        hop_ms = grain_ms
    if hop_ms <= 0:
        return []

    total = len(audio)
    if total <= 0:
        return []

    if end_ms is None:
        end_ms = total
    start_ms = max(0, start_ms)
    end_ms = max(0, min(end_ms, total))
    if end_ms <= start_ms:
        return []

    rng = random.Random(seed)

    grains: List[AudioSegment] = []
    t = start_ms
    while t < end_ms:
        jt = 0
        if jitter_ms > 0:
            jt = rng.randint(-jitter_ms, jitter_ms)

        s = t + jt
        s = max(0, min(s, total))
        e = s + grain_ms

        if e <= total:
            g = audio[s:e]
        else:
            if not pad_end:
                break
            # パディング
            g = audio[s:total] + AudioSegment.silent(duration=e - total)

        # クリック対策：短すぎる場合は fade を抑える
        fm = max(0, int(fade_ms))
        fm = min(fm, len(g) // 2)
        if fm > 0:
            g = g.fade_in(fm).fade_out(fm)

        grains.append(g)
        t += hop_ms

    return grains


def crop(audio: AudioSegment, *, start_ms: int = 0, end_ms: Optional[int] = None) -> AudioSegment:
    """
    単純な切り出しユーティリティ。
    """
    if end_ms is None:
        end_ms = len(audio)
    start_ms = max(0, start_ms)
    end_ms = max(0, min(end_ms, len(audio)))
    if end_ms <= start_ms:
        return AudioSegment.silent(duration=0)
    return audio[start_ms:end_ms]
