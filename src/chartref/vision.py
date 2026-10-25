"""Frame loading, slide segmentation, chart and candlestick detection, pointer tracking."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .models import Bar


def load_frames(path: str, max_fps: float = 10.0) -> tuple[list[np.ndarray], float]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise FileNotFoundError(path)
    src_fps = cap.get(cv2.CAP_PROP_FPS) or max_fps
    stride = max(1, round(src_fps / max_fps))
    frames, i = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if i % stride == 0:
            frames.append(f)
        i += 1
    cap.release()
    return frames, src_fps / stride


def split_slides(frames: list[np.ndarray], change_ratio: float = 0.03) -> list[tuple[int, int]]:
    """Return [start, end) frame ranges.

    A slide change is a frame where more than `change_ratio` of pixels change at once. A moving
    mouse pointer changes far less than 1% of the frame, so it never triggers a cut.
    """
    small = [cv2.cvtColor(cv2.resize(f, (320, 180), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY) for f in frames]
    cuts = [0]
    for i in range(1, len(small)):
        diff = cv2.absdiff(small[i], small[i - 1])
        if (diff > 25).mean() > change_ratio and i - cuts[-1] >= 5:
            cuts.append(i)
    cuts.append(len(frames))
    return [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a >= 5]


def static_background(frames: list[np.ndarray]) -> np.ndarray:
    """Per-pixel median over the slide: removes the moving pointer and leaves the chart."""
    sample = frames[:: max(1, len(frames) // 60)]
    return np.median(np.stack(sample), axis=0).astype(np.uint8)


def candle_mask(img: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    colored = (s > 90) & (v > 60)
    green = colored & (h >= 35) & (h <= 85)
    red = colored & ((h <= 10) | (h >= 165))
    return (green | red).astype(np.uint8) * 255, green, red


def find_plot_area(img: np.ndarray) -> tuple[int, int, int, int]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, th = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        if w * h > 0.2 * img.shape[0] * img.shape[1]:
            return x, y, x + w, y + h
    mask, _, _ = candle_mask(img)
    ys, xs = np.nonzero(mask)
    return int(xs.min()) - 20, int(ys.min()) - 20, int(xs.max()) + 20, int(ys.max()) + 20


def detect_bars(img: np.ndarray, plot: tuple[int, int, int, int]) -> tuple[list[Bar], float]:
    x0, y0, x1, y1 = plot
    mask, green, red = candle_mask(img)
    roi = mask[y0:y1, x0:x1] > 0
    cols = roi.sum(axis=0) >= 2
    runs, start = [], None
    for x, on in enumerate(list(cols) + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            if x - start >= 4:
                runs.append((start, x - 1))
            start = None
    bars = []
    for i, (a, b) in enumerate(runs, start=1):
        sub = roi[:, a: b + 1]
        ys = np.nonzero(sub.any(axis=1))[0]
        xa, xb = a + x0, b + x0
        g = green[y0:y1, xa: xb + 1].sum(); r = red[y0:y1, xa: xb + 1].sum()
        bars.append(Bar(bar_id=i, x_center=(xa + xb) // 2, x_left=xa, x_right=xb,
                        body_top=int(ys.min()) + y0, body_bottom=int(ys.max()) + y0,
                        direction="bull" if g >= r else "bear"))
    spacing = float(np.median(np.diff([b.x_center for b in bars]))) if len(bars) > 1 else 20.0
    return bars, spacing


@dataclass
class PointerSample:
    frame: int
    x: int | None
    y: int | None


def track_pointer(frames: list[np.ndarray], background: np.ndarray, offset: int) -> list[PointerSample]:
    """Pointer = the small moving blob that differs from the static slide; tip = its top-left point."""
    bg = cv2.cvtColor(background, cv2.COLOR_BGR2GRAY)
    kernel = np.ones((2, 2), np.uint8)
    out = []
    for i, f in enumerate(frames):
        diff = cv2.absdiff(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), bg)
        _, th = cv2.threshold(diff, 40, 255, cv2.THRESH_BINARY)
        th = cv2.morphologyEx(th, cv2.MORPH_OPEN, kernel)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(th)
        best = None
        for k in range(1, n):
            area = stats[k, cv2.CC_STAT_AREA]
            w, h = stats[k, cv2.CC_STAT_WIDTH], stats[k, cv2.CC_STAT_HEIGHT]
            if 15 <= area <= 1500 and w <= 60 and h <= 60:
                if best is None or area > stats[best, cv2.CC_STAT_AREA]:
                    best = k
        if best is None:
            out.append(PointerSample(offset + i, None, None))
            continue
        ys, xs = np.nonzero(labels == best)
        top = ys.min()
        tip_x = int(xs[ys <= top + 1].min())
        out.append(PointerSample(offset + i, tip_x, int(top)))
    return out
