"""Human review page: approve, correct or reject each labelled reference before it enters the dataset.

Run:  python review/app.py outputs/demo
Then open http://127.0.0.1:5050
Decisions are saved to <run>/reviews.json; GET /export returns only approved/corrected examples.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template_string, request, send_from_directory

RUN = Path(sys.argv[1] if len(sys.argv) > 1 else "outputs/demo").resolve()
app = Flask(__name__)

PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Chart reference review</title>
<style>
body{font-family:system-ui,sans-serif;margin:24px;background:#f6f6f4;color:#222}
h1{font-size:20px} .stats{margin:8px 0 20px;color:#555}
.card{background:#fff;border:1px solid #ddd;border-radius:8px;padding:14px;margin-bottom:14px;display:flex;gap:16px}
.card img{max-width:420px;border:1px solid #eee} .meta{flex:1}
.tag{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;margin-right:6px}
.label{background:#e3f4e1;color:#1d6b14} .abstain{background:#fdf0dc;color:#8a5300}
.done{background:#e8eefc;color:#2747a8} button{margin-right:6px} input{width:120px}
</style></head><body>
<h1>Chart reference review — {{ run }}</h1>
<div class="stats">{{ n_label }} labelled · {{ n_abstain }} abstained · {{ n_reviewed }} reviewed ·
<a href="/export">export approved dataset (JSON)</a></div>
{% for r in refs %}
<div class="card">
  {% if r.crop_path %}<img src="/file/{{ r.crop_path }}">{% else %}<div style="width:420px;color:#999">no crop (abstained)</div>{% endif %}
  <div class="meta">
    <span class="tag {{ r.decision }}">{{ r.decision }}</span>
    {% if reviews.get(r.segment_index|string) %}<span class="tag done">reviewed: {{ reviews[r.segment_index|string].status }} {{ reviews[r.segment_index|string].bar_ids }}</span>{% endif %}
    <p><b>{{ "%.1f"|format(r.start_s) }}s</b> · slide {{ r.slide }} · “{{ r.transcript }}”</p>
    <p>Phrase: <b>{{ r.phrase }}</b> → bars <b>{{ r.bar_ids }}</b> · confidence {{ r.confidence }}<br><small>{{ r.reason }}</small></p>
    <form method="post" action="/review/{{ r.segment_index }}">
      <button name="status" value="approved" {% if r.decision != 'label' %}disabled{% endif %}>Approve</button>
      <input name="bar_ids" placeholder="e.g. 8,9,10"><button name="status" value="corrected">Save correction</button>
      <button name="status" value="rejected">Reject</button>
    </form>
  </div>
</div>
{% endfor %}
</body></html>"""


def _load():
    report = json.loads((RUN / "references.json").read_text())
    rp = RUN / "reviews.json"
    reviews = json.loads(rp.read_text()) if rp.exists() else {}
    return report, reviews


@app.get("/")
def index():
    report, reviews = _load()
    refs = report["references"]
    class R(dict):
        __getattr__ = dict.get
    return render_template_string(PAGE, run=RUN.name, refs=[R(r) for r in refs], reviews={k: R(v) for k, v in reviews.items()},
                                  n_label=sum(r["decision"] == "label" for r in refs),
                                  n_abstain=sum(r["decision"] == "abstain" for r in refs), n_reviewed=len(reviews))


@app.post("/review/<int:seg>")
def review(seg: int):
    report, reviews = _load()
    ref = next((r for r in report["references"] if r["segment_index"] == seg), None)
    if ref is None:
        abort(404)
    status = request.form.get("status")
    if status not in ("approved", "corrected", "rejected"):
        abort(400)
    if status == "corrected":
        try:
            ids = [int(x) for x in request.form.get("bar_ids", "").replace(" ", "").split(",") if x]
        except ValueError:
            abort(400)
        if not ids:
            abort(400)
    elif status == "approved":
        if ref["decision"] != "label":
            abort(400)
        ids = ref["bar_ids"]
    else:
        ids = []
    reviews[str(seg)] = {"status": status, "bar_ids": ids}
    (RUN / "reviews.json").write_text(json.dumps(reviews, indent=2))
    return redirect("/")


@app.get("/export")
def export():
    report, reviews = _load()
    out = []
    for r in report["references"]:
        rv = reviews.get(str(r["segment_index"]))
        if rv and rv["status"] in ("approved", "corrected"):
            out.append({**r, "bar_ids": rv["bar_ids"], "review_status": rv["status"]})
    return jsonify({"video": report["video"], "examples": out})


@app.get("/file/<path:p>")
def file(p: str):
    return send_from_directory(RUN, p)


if __name__ == "__main__":
    app.run(port=5050)
