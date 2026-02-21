# processing/pan.py
from __future__ import annotations

import math
import random
from typing import List, Optional, Sequence
from pydub import AudioSegment


def extreme_pan(grains: Sequence[AudioSegment], *, amount: float = 0.8) -> List[AudioSegment]:
    """
    左右に交互に振り切る。
    amount は 0.0〜1.0 推奨。
    """
    amount = max(0.0, min(1.0, float(amount)))
    return [g.pan(-amount) if i % 2 == 0 else g.pan(amount) for i, g in enumerate(grains)]


def dynamics_pan(grains: Sequence[AudioSegment], *, cycles: float = 8.0) -> List[AudioSegment]:
    """
    サイン波で連続的にパンを動かす（左右交互成分を混ぜると動きが出る）。
    """
    N = len(grains)
    if N == 0:
        return []
    out: List[AudioSegment] = []
    for i, g in enumerate(grains):
        p = math.sin(2.0 * math.pi * cycles * i / N)
        # 偶数/奇数で位相を反転（あなたの元コードの意図を保持）
        p = p if (i % 2 == 0) else -p
        out.append(g.pan(float(p)))
    return out


def state_pan(grains: Sequence[AudioSegment], *, states: Optional[Sequence[float]] = None) -> List[AudioSegment]:
    """
    離散状態（例: -1,-0.5,0,0.5,1）で順にパン。
    """
    if states is None:
        states = (-1.0, -0.5, 0.0, 0.5, 1.0)
    states = [max(-1.0, min(1.0, float(s))) for s in states]
    if not states:
        return list(grains)
    return [g.pan(states[i % len(states)]) for i, g in enumerate(grains)]


def random_state_pan(
    grains: Sequence[AudioSegment],
    *,
    states: Optional[Sequence[float]] = None,
    seed: Optional[int] = None
) -> List[AudioSegment]:
    """
    離散状態からランダムにパン。
    """
    if states is None:
        states = (-1.0, -0.5, 0.0, 0.5, 1.0)
    states = [max(-1.0, min(1.0, float(s))) for s in states]
    if not states:
        return list(grains)

    rng = random.Random(seed)
    return [g.pan(rng.choice(states)) for g in grains]


def random_pan(grains: Sequence[AudioSegment], *, seed: Optional[int] = None) -> List[AudioSegment]:
    """
    -1.0〜1.0 の連続一様でランダムパン。
    """
    rng = random.Random(seed)
    return [g.pan(rng.uniform(-1.0, 1.0)) for g in grains]
