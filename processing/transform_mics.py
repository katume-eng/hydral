# processing/transform.py
from __future__ import annotations

import random
from typing import List, Optional, Sequence, Tuple
from pydub import AudioSegment


def shuffle(grains: Sequence[AudioSegment], *, seed: Optional[int] = None) -> List[AudioSegment]:
    """
    grains をシャッフルして返す（元リストは破壊しない）。
    """
    rng = random.Random(seed)
    out = list(grains)
    rng.shuffle(out)
    return out


def reverse_some(grains: Sequence[AudioSegment], *, prob: float = 0.2, seed: Optional[int] = None) -> List[AudioSegment]:
    """
    確率 prob で反転する。
    """
    prob = max(0.0, min(1.0, float(prob)))
    rng = random.Random(seed)
    return [g.reverse() if rng.random() < prob else g for g in grains]


def gain_random(
    grains: Sequence[AudioSegment],
    *,
    min_db: float = -6.0,
    max_db: float = 6.0,
    seed: Optional[int] = None
) -> List[AudioSegment]:
    """
    各グレインにランダムゲイン（dB）を適用。
    """
    rng = random.Random(seed)
    lo, hi = float(min_db), float(max_db)
    if hi < lo:
        lo, hi = hi, lo
    return [g.apply_gain(rng.uniform(lo, hi)) for g in grains]


def drop_some(grains: Sequence[AudioSegment], *, prob: float = 0.1, seed: Optional[int] = None) -> List[AudioSegment]:
    """
    確率 prob でグレインを落とす（無音化ではなく除去）。
    """
    prob = max(0.0, min(1.0, float(prob)))
    rng = random.Random(seed)
    return [g for g in grains if rng.random() >= prob]


def repeat_some(
    grains: Sequence[AudioSegment],
    *,
    prob: float = 0.1,
    times: int = 2,
    seed: Optional[int] = None
) -> List[AudioSegment]:
    """
    確率 prob で同じグレインを times 回繰り返して挿入する（いわゆる簡易スタッター）。
    """
    prob = max(0.0, min(1.0, float(prob)))
    times = max(1, int(times))
    rng = random.Random(seed)
    out: List[AudioSegment] = []
    for g in grains:
        if rng.random() < prob:
            out.extend([g] * times)
        else:
            out.append(g)
    return out


def stutter(
    grains: Sequence[AudioSegment],
    *,
    every: int = 16,
    width: int = 3
) -> List[AudioSegment]:
    """
    定期的に「直前のグレイン」を width 個追加して吃る。
    - every: 何個ごとに発生させるか
    - width: 追加回数
    """
    every = max(1, int(every))
    width = max(1, int(width))
    out: List[AudioSegment] = []
    for i, g in enumerate(grains):
        out.append(g)
        if (i + 1) % every == 0:
            out.extend([g] * width)
    return out


def fade_grains(grains: Sequence[AudioSegment], *, fade_ms: int = 5) -> List[AudioSegment]:
    """
    全グレインにフェードを適用（クリック対策の後掛け）。
    """
    fm = max(0, int(fade_ms))
    out: List[AudioSegment] = []
    for g in grains:
        f = min(fm, len(g) // 2)
        out.append(g.fade_in(f).fade_out(f) if f > 0 else g)
    return out


def limit_length(
    grains: Sequence[AudioSegment],
    *,
    max_grains: Optional[int] = None,
    max_duration_ms: Optional[int] = None
) -> List[AudioSegment]:
    """
    グレイン数 or 合計時間でカットする安全装置。
    """
    out: List[AudioSegment] = []
    total = 0

    for g in grains:
        if max_grains is not None and len(out) >= max_grains:
            break
        if max_duration_ms is not None and total >= max_duration_ms:
            break
        out.append(g)
        total += len(g)

    if max_duration_ms is not None and total > max_duration_ms and out:
        # 最後のグレインを切って合わせる
        overflow = total - max_duration_ms
        if overflow > 0:
            out[-1] = out[-1][:-overflow]
    return out
