"""Score references.json against the synthetic answer key.

Definitions (precision first, as the brief asks):
  precision         = correct labels / all labels emitted
  coverage          = correct labels / real references in the answer key
  correct abstains  = ambiguous moments where the pipeline abstained
  false labels      = labels emitted on ambiguous or non-reference moments
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def score(refs_path: str, key_path: str) -> dict:
    refs = {r["segment_index"]: r for r in json.loads(Path(refs_path).read_text())["references"]}
    key = json.loads(Path(key_path).read_text())["segments"]
    rows, correct, wrong, emitted, real, amb, amb_ok, false_lab, missed = [], 0, 0, 0, 0, 0, 0, 0, 0
    for seg in key:
        r = refs.get(seg["index"])
        labelled = bool(r and r["decision"] == "label")
        pred = r["bar_ids"] if labelled else None
        truth = seg["truth"]
        emitted += labelled
        if isinstance(truth, dict):
            real += 1
            if labelled and pred == truth["bars"]:
                outcome = "correct"; correct += 1
            elif labelled:
                outcome = "WRONG"; wrong += 1
            else:
                outcome = "missed (abstained)"; missed += 1
        elif truth == "ambiguous":
            amb += 1
            if labelled:
                outcome = "FALSE LABEL"; false_lab += 1
            else:
                outcome = "correct abstain"; amb_ok += 1
        else:
            outcome = "FALSE LABEL" if labelled else "no reference (ignored)"
            false_lab += labelled
        rows.append({"segment": seg["index"], "text": seg["text"], "truth": truth, "predicted": pred,
                     "confidence": r["confidence"] if r else None, "outcome": outcome})
    return {
        "labels_emitted": emitted, "correct": correct, "wrong": wrong, "false_labels": false_lab,
        "precision": round(correct / emitted, 3) if emitted else None,
        "real_references": real, "coverage": round(correct / real, 3) if real else None, "missed": missed,
        "ambiguous_moments": amb, "correct_abstains": amb_ok, "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("references"); ap.add_argument("answer_key")
    ap.add_argument("--out")
    a = ap.parse_args()
    s = score(a.references, a.answer_key)
    for row in s["rows"]:
        print(f'{row["segment"]:>3} {row["outcome"]:<24} pred={row["predicted"]} truth={row["truth"]}  "{row["text"]}"')
    print(f'\nprecision {s["precision"]} ({s["correct"]}/{s["labels_emitted"]} labels correct) | '
          f'coverage {s["coverage"]} ({s["correct"]}/{s["real_references"]} real references) | '
          f'ambiguous moments abstained {s["correct_abstains"]}/{s["ambiguous_moments"]} | false labels {s["false_labels"]}')
    if a.out:
        Path(a.out).write_text(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
