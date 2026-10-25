"""Run the pipeline on N freshly generated synthetic lessons and aggregate the scores."""
import argparse, json, subprocess, sys
from pathlib import Path
sys.path.insert(0, "src")
from chartref.pipeline import run
from evaluate import score

ap = argparse.ArgumentParser(); ap.add_argument("--seeds", type=int, default=10); ap.add_argument("--jitter", type=float, default=1.5)
ap.add_argument("--out", default="outputs/stress")
a = ap.parse_args()
tot = dict(emitted=0, correct=0, wrong=0, false=0, real=0, amb=0, amb_ok=0)
for seed in range(1, a.seeds + 1):
    d = Path(a.out) / f"j{a.jitter}_s{seed}"
    subprocess.run([sys.executable, "demo/generate.py", "--out", str(d), "--seed", str(seed), "--jitter", str(a.jitter)], check=True, capture_output=True)
    run(str(d / "chart_lesson.mp4"), str(d / "chart_lesson.srt"), str(d / "out"), preview=False)
    s = score(str(d / "out/references.json"), str(d / "answer_key.json"))
    for k, v in [("emitted","labels_emitted"),("correct","correct"),("wrong","wrong"),("false","false_labels"),("real","real_references"),("amb","ambiguous_moments"),("amb_ok","correct_abstains")]:
        tot[k] += s[v]
    print(f"seed {seed}: precision {s['precision']} coverage {s['coverage']} abstain {s['correct_abstains']}/{s['ambiguous_moments']} wrong {s['wrong']} false {s['false_labels']}")
res = {"seeds": a.seeds, "jitter_px": a.jitter, **tot,
       "precision": round(tot["correct"] / tot["emitted"], 3), "coverage": round(tot["correct"] / tot["real"], 3)}
print(json.dumps(res))
Path(a.out).mkdir(parents=True, exist_ok=True)
(Path(a.out) / f"summary_jitter{a.jitter}.json").write_text(json.dumps(res, indent=2))
