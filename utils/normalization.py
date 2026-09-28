"""
utils/normalization.py
=======================
Small, generic, well-documented math helpers. These are intentionally dumb
and reusable -- all the *meaning* (which field, which center, which scale,
which categorical mapping) lives in the driver definitions in
scoring_engine.py, not here. That separation is what makes every score
"mathematically reproducible from the displayed components".
"""

from typing import Dict, Optional


def clip(x: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def linear_score(x: float, center: float, scale: float, cap: float = 100.0) -> float:
    """Linear map centered at `center`; `scale` is the distance from center
    that maps to a full +/-100 score (before capping to +/-cap)."""
    if scale == 0:
        return 0.0
    return clip(((x - center) / scale) * 100.0, -cap, cap)


def categorical_score(value: Optional[str], mapping: Dict[str, float]) -> Optional[float]:
    if value is None:
        return None
    return mapping.get(value)


def average(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return sum(values) / len(values)


def weighted_average(pairs):
    """pairs: iterable of (value, weight). Ignores entries where value is None."""
    total_w = 0.0
    total = 0.0
    for v, w in pairs:
        if v is None or w is None:
            continue
        total += v * w
        total_w += w
    if total_w == 0:
        return None
    return total / total_w
