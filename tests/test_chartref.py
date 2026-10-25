"""Unit and end-to-end tests. Run: PYTHONPATH=src python -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from chartref.models import Bar  # noqa: E402
from chartref.resolve import resolve  # noqa: E402
from chartref.transcript import find_mention, parse_srt  # noqa: E402
from chartref.vision import PointerSample  # noqa: E402

PLOT = (0, 0, 1000, 500)
BARS = [Bar(bar_id=i, x_center=30 * i, x_left=30 * i - 7, x_right=30 * i + 7, body_top=100, body_bottom=120,
            direction="bull") for i in range(1, 31)]


def samples(xs, y=110):
    return [PointerSample(i, x, None if x is None else y) for i, x in enumerate(xs)]


class TestTranscript(unittest.TestCase):
    def test_singular(self):
        m = find_mention("Look at this bar, a strong trend bar.")
        self.assertFalse(m.plural); self.assertEqual(m.expected_count, 1)

    def test_counted_plural(self):
        m = find_mention("These three bars form a tight pullback.")
        self.assertTrue(m.plural); self.assertEqual(m.expected_count, 3)

    def test_copula_and_here(self):
        self.assertEqual(find_mention("This is the second entry buy setup.").phrase, "This is the second entry")
        self.assertEqual(find_mention("I would buy here above it.").phrase, "buy here")

    def test_region_noun_is_plural(self):
        self.assertTrue(find_mention("This wedge has three pushes.").plural)

    def test_no_reference(self):
        self.assertIsNone(find_mention("Here we are in a clear bull trend."))
        self.assertIsNone(find_mention("That is the end of the lesson."))

    def test_parse_srt(self):
        with tempfile.NamedTemporaryFile("w", suffix=".srt", delete=False) as f:
            f.write("1\n00:00:01,500 --> 00:00:03,000\nThis bar.\n\n2\n00:01:00,000 --> 00:01:02,250\nThese bars.\n")
        segs = parse_srt(f.name)
        self.assertEqual([(s.start, s.end) for s in segs], [(1.5, 3.0), (60.0, 62.25)])


class TestResolver(unittest.TestCase):
    def test_dwell_on_bar(self):
        d, ids, conf, *_ = resolve(find_mention("this bar"), samples([150, 151, 149, 150] * 5), BARS, 30, PLOT)
        self.assertEqual((d, ids), ("label", [5])); self.assertGreaterEqual(conf, 0.9)

    def test_between_bars_abstains(self):
        d, ids, *_ = resolve(find_mention("this bar"), samples([165] * 20), BARS, 30, PLOT)
        self.assertEqual(d, "abstain")

    def test_moving_pointer_abstains(self):
        d, *_ = resolve(find_mention("this bar"), samples(list(range(100, 700, 30))), BARS, 30, PLOT)
        self.assertEqual(d, "abstain")

    def test_off_chart_abstains(self):
        d, _, _, reason, ratio = resolve(find_mention("this bar"), samples([None] * 20), BARS, 30, PLOT)
        self.assertEqual(d, "abstain"); self.assertEqual(ratio, 0.0)

    def test_sweep_matches_count(self):
        d, ids, *_ = resolve(find_mention("these three bars"), samples([240, 240, 255, 270, 285, 300, 300]), BARS, 30, PLOT)
        self.assertEqual((d, ids), ("label", [8, 9, 10]))

    def test_sweep_count_mismatch_abstains(self):
        d, ids, _, reason, _ = resolve(find_mention("these two bars"), samples([240, 270, 300, 300]), BARS, 30, PLOT)
        self.assertEqual(d, "abstain"); self.assertIn("heard 2", reason)


class TestEndToEnd(unittest.TestCase):
    def test_synthetic_lesson_precision(self):
        from chartref.pipeline import run
        from evaluate import score
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(ROOT / "demo/generate.py"), "--out", tmp, "--seed", "3"], check=True,
                           capture_output=True)
            run(f"{tmp}/chart_lesson.mp4", f"{tmp}/chart_lesson.srt", f"{tmp}/out", preview=False)
            report = json.loads(Path(f"{tmp}/out/references.json").read_text())
            self.assertEqual(len(report["slides"]), 2)
            self.assertTrue(all(len(s["bars"]) == 36 for s in report["slides"]))
            s = score(f"{tmp}/out/references.json", f"{tmp}/answer_key.json")
            self.assertEqual(s["false_labels"], 0); self.assertEqual(s["wrong"], 0)
            self.assertEqual(s["precision"], 1.0); self.assertGreaterEqual(s["coverage"], 0.9)


class TestReviewApp(unittest.TestCase):
    def test_approve_correct_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / "references.json").write_text(json.dumps({"video": "v.mp4", "references": [
                {"segment_index": 2, "slide": 1, "start_s": 1.0, "end_s": 2.0, "transcript": "this bar", "phrase": "this bar",
                 "decision": "label", "bar_ids": [5], "confidence": 0.9, "reason": "ok", "crop_path": None},
                {"segment_index": 3, "slide": 1, "start_s": 2.0, "end_s": 3.0, "transcript": "this one", "phrase": "this one",
                 "decision": "abstain", "bar_ids": [], "confidence": 0.0, "reason": "between", "crop_path": None}]}))
            sys.argv = ["app.py", str(run_dir)]
            import importlib
            import review.app as appmod
            importlib.reload(appmod)
            c = appmod.app.test_client()
            self.assertEqual(c.get("/").status_code, 200)
            self.assertEqual(c.post("/review/3", data={"status": "approved"}).status_code, 400)  # can't approve an abstain
            c.post("/review/2", data={"status": "approved"})
            c.post("/review/3", data={"status": "corrected", "bar_ids": "17, 18"})
            ex = c.get("/export").get_json()["examples"]
            self.assertEqual([(e["segment_index"], e["bar_ids"]) for e in ex], [(2, [5]), (3, [17, 18])])


if __name__ == "__main__":
    unittest.main()
