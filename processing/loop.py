# processing/loop.py
from __future__ import annotations

from typing import Optional, Sequence
from pydub import AudioSegment


def loop_audio(
    audio: AudioSegment,
    *,
    duration_ms: int,
    crossfade_ms: int = 10
) -> AudioSegment:
    """
    audio を duration_ms になるまでループして埋める。
    """
    if duration_ms <= 0:
        return AudioSegment.silent(duration=0)
    if len(audio) <= 0:
        return AudioSegment.silent(duration=duration_ms)

    out = AudioSegment.silent(duration=0)
    while len(out) < duration_ms:
        if len(out) == 0:
            out = audio
        else:
            cf = min(crossfade_ms, len(out), len(audio))
            out = out.append(audio, crossfade=cf)

    return out[:duration_ms]


def loop_grains(
    grains: Sequence[AudioSegment],
    *,
    repeats: Optional[int] = None,
    duration_ms: Optional[int] = None,
    crossfade_ms: int = 0
) -> AudioSegment:
    """
    grains を繰り返して連結する。
    - repeats: 回数指定（duration_ms 未指定時に有効）
    - duration_ms: 長さ指定（repeats 無視、必要なだけ回して切る）
    """
    if not grains:
        return AudioSegment.silent(duration=0)

    def append(out: AudioSegment, g: AudioSegment) -> AudioSegment:
        if crossfade_ms <= 0 or len(out) == 0:
            return out + g
        cf = min(crossfade_ms, len(out), len(g))
        return out.append(g, crossfade=cf)

    if duration_ms is not None:
        if duration_ms <= 0:
            return AudioSegment.silent(duration=0)
        out = AudioSegment.silent(duration=0)
        i = 0
        while len(out) < duration_ms:
            out = append(out, grains[i % len(grains)])
            i += 1
        return out[:duration_ms]

    if repeats is None:
        repeats = 1
    if repeats <= 0:
        return AudioSegment.silent(duration=0)

    out = AudioSegment.silent(duration=0)
    for _ in range(repeats):
        for g in grains:
            out = append(out, g)
    return out
