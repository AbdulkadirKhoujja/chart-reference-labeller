"""Resolve each spoken reference to the bars under the pointer, or abstain.

Precision over recall: a label is only emitted when the pointer clearly
indicates the bars. Every other case abstains with a stated reason.
"""
from __future__ import annotations

import numpy as np

from .models import Bar
from .transcript import Mention
from .vision import PointerSample


def resolve(mention: Mention, samples: list[PointerSample], bars: list[Bar], spacing: float,
            plot: tuple[int, int, int, int]) -> tuple[str, list[int], float, str, float]:
    """Return (decision, bar_ids, confidence, reason, on_chart_ratio)."""
    x0, y0, x1, y1 = plot
    pts = [(s.x, s.y) for s in samples if s.x is not None and x0 <= s.x <= x1 and y0 <= s.y <= y1]
    on_ratio = len(pts) / max(1, len(samples))
    if on_ratio < 0.5:
        return "abstain", [], 0.0, "pointer was not on the chart while the phrase was spoken", on_ratio
    xs = np.array([p[0] for p in pts], float)
    centers = np.array([b.x_center for b in bars], float)
    half = spacing / 2

    if not mention.plural:
        speed = np.abs(np.diff(xs)) if len(xs) > 1 else np.array([0.0])
        dwell = xs[1:][speed <= 3] if len(xs) > 1 else xs
        dwell_ratio = len(dwell) / max(1, len(xs) - 1)
        if dwell_ratio < 0.4:
            return "abstain", [], 0.0, "pointer kept moving; it never settled on one bar", on_ratio
        q1, q3 = np.percentile(dwell, [25, 75])
        if q3 - q1 > 0.5 * spacing:
            return "abstain", [], 0.0, "pointer rested in more than one place", on_ratio
        x = float(np.median(dwell))
        i = int(np.argmin(np.abs(centers - x)))
        offset = abs(centers[i] - x) / half  # 0 = on the bar centre, 1 = midway between bars
        if offset > 0.5:
            return "abstain", [], round(1 - offset, 3), "pointer was between two bars", on_ratio
        conf = round(float(min(1.0, (1 - offset) * min(1.0, dwell_ratio / 0.7) * min(1.0, on_ratio / 0.8))), 3)
        return "label", [bars[i].bar_id], conf, "pointer rested on the bar", on_ratio

    lo, hi = np.percentile(xs, [5, 95])
    covered = [b.bar_id for b, c in zip(bars, centers) if lo - 0.35 * spacing <= c <= hi + 0.35 * spacing]
    if len(covered) < 2:
        return "abstain", covered, 0.0, "plural phrase but the pointer covered fewer than two bars", on_ratio
    if mention.expected_count and mention.expected_count != len(covered):
        return ("abstain", covered, 0.3,
                f"heard {mention.expected_count} bars but the pointer swept {len(covered)}", on_ratio)
    conf = round(float(min(1.0, on_ratio / 0.8) * (1.0 if mention.expected_count else 0.85)), 3)
    return "label", covered, conf, "pointer swept across the bars", on_ratio
