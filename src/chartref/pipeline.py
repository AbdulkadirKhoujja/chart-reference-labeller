"""End-to-end: video + transcript -> validated JSON references, crops and an annotated preview video."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import cv2
import numpy as np

from .models import Reference, Report, Slide
from .resolve import resolve
from .transcript import find_mention, parse_srt
from .vision import detect_bars, find_plot_area, load_frames, split_slides, static_background, track_pointer


def run(video: str, srt: str, out_dir: str, threshold: float = 0.6, preview: bool = True) -> Report:
    out = Path(out_dir); (out / "crops").mkdir(parents=True, exist_ok=True)
    frames, fps = load_frames(video)
    slides_out, per_slide = [], []
    for s_idx, (a, b) in enumerate(split_slides(frames), start=1):
        bg = static_background(frames[a:b])
        plot = find_plot_area(bg)
        bars, spacing = detect_bars(bg, plot)
        samples = track_pointer(frames[a:b], bg, a)
        slides_out.append(Slide(slide=s_idx, start_s=round(a / fps, 2), end_s=round(b / fps, 2),
                                plot_area=plot, bar_spacing_px=round(spacing, 2), bars=bars))
        per_slide.append((a, b, bg, plot, bars, spacing, samples))

    refs = []
    for seg in parse_srt(srt):
        mention = find_mention(seg.text)
        if mention is None:
            continue
        fa, fb = int(seg.start * fps), int(seg.end * fps)
        match = next(((i, p) for i, p in enumerate(per_slide) if p[0] <= fa < p[1]), None)
        if match is None:
            continue
        i, (a, b, bg, plot, bars, spacing, samples) = match
        window = [s for s in samples if fa <= s.frame < fb]
        decision, ids, conf, reason, on_ratio = resolve(mention, window, bars, spacing, plot)
        if decision == "label" and conf < threshold:
            decision, reason = "abstain", f"confidence {conf} below threshold {threshold}; " + reason
        crop = _crop(bg, bars, ids, window, plot, out / "crops" / f"seg{seg.index:03d}.png") if ids else None
        refs.append(Reference(
            segment_index=seg.index, slide=i + 1, start_s=seg.start, end_s=seg.end, transcript=seg.text,
            phrase=mention.phrase, expected_count=mention.expected_count, decision=decision,
            bar_ids=ids if decision == "label" else [], confidence=conf, reason=reason,
            pointer_on_chart_ratio=round(on_ratio, 3), crop_path=str(crop.relative_to(out)) if crop else None))

    report = Report(video=video, transcript=srt, fps=fps, frames=len(frames), confidence_threshold=threshold,
                    slides=slides_out, references=refs)
    (out / "references.json").write_text(report.model_dump_json(indent=2))
    if preview:
        _preview(frames, fps, per_slide, refs, out / "preview.mp4")
    return report


def _crop(bg, bars, ids, window, plot, path: Path) -> Path:
    img = bg.copy()
    sel = [b for b in bars if b.bar_id in ids]
    for b in sel:
        cv2.rectangle(img, (b.x_left - 3, b.body_top - 3), (b.x_right + 3, b.body_bottom + 3), (0, 140, 255), 2)
        cv2.putText(img, str(b.bar_id), (b.x_left, b.body_bottom + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 100, 220), 1)
    pts = [(s.x, s.y) for s in window if s.x is not None]
    for p, q in zip(pts, pts[1:]):
        cv2.line(img, p, q, (200, 0, 200), 1)
    x0 = max(plot[0], min(b.x_left for b in sel) - 80); x1 = min(plot[2], max(b.x_right for b in sel) + 80)
    y0 = max(plot[1], min(b.body_top for b in sel) - 90); y1 = min(plot[3], max(b.body_bottom for b in sel) + 90)
    cv2.imwrite(str(path), img[y0:y1, x0:x1])
    return path


def _preview(frames, fps, per_slide, refs, path: Path):
    raw = path.with_suffix(".raw.mp4")
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(str(raw), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for fi, f in enumerate(frames):
        img = f.copy()
        sl = next((p for p in per_slide if p[0] <= fi < p[1]), None)
        if sl:
            a, b, bg, plot, bars, spacing, samples = sl
            for bar in bars:
                cv2.putText(img, str(bar.bar_id), (bar.x_center - 6, plot[3] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (120, 120, 120), 1)
            s = samples[fi - a]
            if s.x is not None:
                cv2.circle(img, (s.x, s.y), 6, (200, 0, 200), 2)
            t = fi / fps
            ref = next((r for r in refs if r.start_s <= t < r.end_s), None)
            if ref:
                ok = ref.decision == "label"
                label = (f'"{ref.phrase}" -> bars {ref.bar_ids} (conf {ref.confidence})' if ok
                         else f'"{ref.phrase}" -> ABSTAIN: {ref.reason}')
                cv2.rectangle(img, (0, h - 46), (w, h), (30, 30, 30), -1)
                cv2.putText(img, label, (16, h - 16), cv2.FONT_HERSHEY_SIMPLEX, 0.62,
                            (90, 220, 90) if ok else (80, 180, 255), 1, cv2.LINE_AA)
                if ok:
                    for bar in bars:
                        if bar.bar_id in ref.bar_ids:
                            cv2.rectangle(img, (bar.x_left - 3, bar.body_top - 3), (bar.x_right + 3, bar.body_bottom + 3), (0, 140, 255), 2)
        vw.write(img)
    vw.release()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "23", "-pix_fmt", "yuv420p", str(path)], check=True)
    raw.unlink()


def main():
    ap = argparse.ArgumentParser(description="Resolve spoken chart references to bars.")
    ap.add_argument("video"); ap.add_argument("transcript")
    ap.add_argument("--out", default="outputs/run")
    ap.add_argument("--threshold", type=float, default=0.6)
    ap.add_argument("--no-preview", action="store_true")
    a = ap.parse_args()
    r = run(a.video, a.transcript, a.out, a.threshold, not a.no_preview)
    lab = sum(x.decision == "label" for x in r.references)
    print(f"{len(r.slides)} slides, {sum(len(s.bars) for s in r.slides)} bars, "
          f"{len(r.references)} references: {lab} labelled, {len(r.references) - lab} abstained -> {a.out}")


if __name__ == "__main__":
    main()
