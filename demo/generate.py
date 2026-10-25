"""Generate a synthetic narrated trading-chart teaching video with a known answer key.

Everything here is synthetic: random OHLC data, a drawn mouse pointer and a
scripted transcript. The answer key records which bars each spoken reference
points at, and marks deliberately ambiguous moments where the correct
behaviour is to abstain.

Outputs (in --out):
  chart_lesson.mp4      1280x720, 10 fps
  chart_lesson.srt      transcript (one sentence per segment)
  answer_key.json       ground truth per transcript segment
"""
from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1280, 720, 10
PLOT = (90, 110, 1190, 640)  # x0, y0, x1, y1
N_BARS = 36
GREEN = (60, 160, 40)   # BGR
RED = (50, 50, 210)
WICK = (90, 90, 90)
EMA = (200, 120, 30)


def make_ohlc(rng: random.Random, n: int) -> list[tuple[float, float, float, float]]:
    bars, price = [], 100.0
    drift = rng.choice([-0.4, 0.4])
    for i in range(n):
        if i % 9 == 0:
            drift = rng.uniform(-0.6, 0.6)
        o = price
        c = o + drift + rng.gauss(0, 1.1)
        if abs(c - o) < 0.25:  # keep bodies visible
            c = o + (0.3 if rng.random() > 0.5 else -0.3)
        hi = max(o, c) + abs(rng.gauss(0, 0.6))
        lo = min(o, c) - abs(rng.gauss(0, 0.6))
        bars.append((o, hi, lo, c))
        price = c
    return bars


def bar_geometry(ohlc):
    x0, y0, x1, y1 = PLOT
    lo = min(b[2] for b in ohlc)
    hi = max(b[1] for b in ohlc)
    pad = (hi - lo) * 0.08
    lo, hi = lo - pad, hi + pad
    sy = lambda p: int(y1 - (p - lo) / (hi - lo) * (y1 - y0))
    step = (x1 - x0) / (len(ohlc) + 1)
    geo = []
    for i, (o, h, l, c) in enumerate(ohlc):
        cx = int(x0 + step * (i + 1))
        geo.append({"id": i + 1, "cx": cx, "o": sy(o), "h": sy(h), "l": sy(l), "c": sy(c), "bull": c >= o})
    return geo, step


def draw_slide(title: str, ohlc, annotations: list[tuple[int, str]]):
    img = np.full((H, W, 3), 245, np.uint8)
    x0, y0, x1, y1 = PLOT
    cv2.rectangle(img, (x0, y0), (x1, y1), (255, 255, 255), -1)
    for gy in range(y0, y1, 53):
        cv2.line(img, (x0, gy), (x1, gy), (225, 225, 225), 1)
    cv2.rectangle(img, (x0, y0), (x1, y1), (150, 150, 150), 1)
    cv2.putText(img, title, (x0, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2, cv2.LINE_AA)
    geo, step = bar_geometry(ohlc)
    half = max(4, int(step * 0.28))
    # EMA line
    closes = [b[3] for b in ohlc]
    ema, k, pts = closes[0], 2 / (20 + 1), []
    lo = min(b[2] for b in ohlc); hi = max(b[1] for b in ohlc); pad = (hi - lo) * 0.08
    for g, c in zip(geo, closes):
        ema = c * k + ema * (1 - k)
        y = int(y1 - (ema - (lo - pad)) / ((hi + pad) - (lo - pad)) * (y1 - y0))
        pts.append((g["cx"], y))
    cv2.polylines(img, [np.array(pts, np.int32)], False, EMA, 2, cv2.LINE_AA)
    for g in geo:
        cv2.line(img, (g["cx"], g["h"]), (g["cx"], g["l"]), WICK, 1)
        top, bot = min(g["o"], g["c"]), max(g["o"], g["c"])
        if bot - top < 3:
            bot = top + 3
        cv2.rectangle(img, (g["cx"] - half, top), (g["cx"] + half, bot), GREEN if g["bull"] else RED, -1)
    for bar_id, text in annotations:
        g = geo[bar_id - 1]
        cv2.putText(img, text, (g["cx"] - 30, max(y0 + 20, g["h"] - 30)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1, cv2.LINE_AA)
        cv2.arrowedLine(img, (g["cx"], max(y0 + 25, g["h"] - 25)), (g["cx"], g["h"] - 4), (30, 30, 30), 1, tipLength=0.3)
    return img, geo, step


CURSOR = np.array([(0, 0), (0, 17), (4, 13), (7, 20), (10, 19), (7, 12), (12, 12)], np.int32)


def draw_cursor(img, x, y):
    pts = CURSOR + np.array([int(x), int(y)])
    cv2.fillPoly(img, [pts], (255, 255, 255))
    cv2.polylines(img, [pts], True, (0, 0, 0), 1, cv2.LINE_AA)


def bar_point(geo, bar_id):
    g = geo[bar_id - 1]
    return g["cx"], min(g["o"], g["c"]) + 2  # just inside the top of the body


# Each slide's script: list of (sentence, action, truth)
# action: ("hover", bar) | ("sweep", a, b) | ("between", a) | ("offchart",) | ("fast", a, b) | ("idle", bar)
# truth:  list of bar ids, "ambiguous", or None (no reference)
def scripts():
    return [
        ("Slide 1 - Trend and pullbacks", [(12, "H2?")], [
            ("Here we are in a clear bull trend above the moving average.", ("idle", 6), None),
            ("Look at this bar, a strong bull trend bar closing near its high.", ("hover", 5), [5]),
            ("These three bars form a tight pullback.", ("sweep", 8, 10), [8, 9, 10]),
            ("This is the second entry buy setup.", ("hover", 12), [12]),
            ("I would buy here above the signal bar.", ("hover", 13), [13]),
            ("Now this one is harder to read.", ("between", 17), "ambiguous"),
            ("These bars show the market going sideways.", ("sweep", 20, 25), [20, 21, 22, 23, 24, 25]),
            ("This breakout failed quickly.", ("hover", 27), [27]),
            ("And this bar trapped the late bulls.", ("fast", 26, 34), "ambiguous"),
            ("Notice how the moving average flattened out.", ("idle", 30), None),
        ]),
        ("Slide 2 - Trading range and wedge", [(9, "wedge"), (28, "failed BO")], [
            ("This is a trading range, so we expect reversals.", ("idle", 3), None),
            ("This bar is the first push down.", ("hover", 4), [4]),
            ("This wedge has three pushes.", ("sweep", 6, 9), [6, 7, 8, 9]),
            ("I would not take this trade because the location is poor.", ("hover", 15), [15]),
            ("Look at this bar here.", ("offchart",), "ambiguous"),
            ("These two bars are an outside up pattern.", ("sweep", 19, 20), [19, 20]),
            ("This pullback is shallow.", ("hover", 23), [23]),
            ("Was it this bar or the next one?", ("between", 25), "ambiguous"),
            ("This failed breakout is the sell signal.", ("hover", 28), [28]),
            ("That is the end of the lesson.", ("idle", 33), None),
        ]),
    ]


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="demo/assets")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--jitter", type=float, default=1.5, help="pointer hand-shake in pixels while resting")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    raw = out / "_raw.mp4"
    vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    t = 0.0
    srt, key = [], {"fps": FPS, "frame_size": [W, H], "plot_area": PLOT, "slides": [], "segments": []}
    pointer = (W // 2, H // 2)

    for s_idx, (title, ann, lines) in enumerate(scripts(), start=1):
        ohlc = make_ohlc(rng, N_BARS)
        slide, geo, step = draw_slide(title, ohlc, ann)
        key["slides"].append({"slide": s_idx, "title": title, "bars": [{"id": g["id"], "cx": g["cx"]} for g in geo]})
        # 1 s of static slide first
        for _ in range(FPS):
            f = slide.copy(); draw_cursor(f, *pointer); vw.write(f); t += 1 / FPS
        for sentence, action, truth in lines:
            dur = max(2.5, 0.38 * len(sentence.split()))
            move_frames = 8  # pointer travels to its start position before speaking
            kind = action[0]
            if kind in ("hover", "idle"):
                start_pt = bar_point(geo, action[1])
            elif kind in ("sweep", "fast"):
                start_pt = bar_point(geo, action[1])
            elif kind == "between":
                a = geo[action[1] - 1]; b = geo[action[1]]
                start_pt = ((a["cx"] + b["cx"]) // 2, min(a["o"], a["c"], b["o"], b["c"]) + 2)
            else:  # offchart
                start_pt = (W - 150, 60)
            if kind == "idle":  # idle pointer parked outside the plot, not pointing at anything
                start_pt = (PLOT[2] + 40, PLOT[3] - 40)
            for i in range(move_frames):
                e = ease((i + 1) / move_frames)
                p = (pointer[0] + (start_pt[0] - pointer[0]) * e, pointer[1] + (start_pt[1] - pointer[1]) * e)
                f = slide.copy(); draw_cursor(f, *p); vw.write(f); t += 1 / FPS
            pointer = start_pt
            seg_start = t
            n = int(dur * FPS)
            for i in range(n):
                u = i / max(1, n - 1)
                if kind == "sweep":
                    a, b = bar_point(geo, action[1]), bar_point(geo, action[2])
                    # sweep across during the middle 70% of the sentence
                    v = min(1.0, max(0.0, (u - 0.15) / 0.7))
                    p = (a[0] + (b[0] - a[0]) * ease(v), a[1] + (b[1] - a[1]) * ease(v))
                elif kind == "fast":
                    a, b = bar_point(geo, action[1]), bar_point(geo, action[2])
                    v = (math.sin(u * math.pi * 6) + 1) / 2  # rapid back-and-forth, never settles
                    p = (a[0] + (b[0] - a[0]) * v, a[1] + (b[1] - a[1]) * v)
                else:
                    p = (start_pt[0] + rng.uniform(-args.jitter, args.jitter), start_pt[1] + rng.uniform(-args.jitter, args.jitter))
                f = slide.copy(); draw_cursor(f, *p); vw.write(f); t += 1 / FPS
                pointer = (int(p[0]), int(p[1]))
            seg_end = t
            srt.append((seg_start, seg_end, sentence))
            key["segments"].append({
                "index": len(srt), "slide": s_idx, "start": round(seg_start, 2), "end": round(seg_end, 2),
                "text": sentence,
                "truth": truth if truth in (None, "ambiguous") else {"bars": truth},
            })
        for _ in range(FPS):
            f = slide.copy(); draw_cursor(f, *pointer); vw.write(f); t += 1 / FPS
    vw.release()

    final = out / "chart_lesson.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "20", "-pix_fmt", "yuv420p", str(final)], check=True)
    raw.unlink()

    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"
    (out / "chart_lesson.srt").write_text("".join(f"{i}\n{ts(a)} --> {ts(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(srt, 1)))
    (out / "answer_key.json").write_text(json.dumps(key, indent=2))
    print(f"wrote {final} ({t:.1f}s), {len(srt)} transcript segments")


if __name__ == "__main__":
    main()
