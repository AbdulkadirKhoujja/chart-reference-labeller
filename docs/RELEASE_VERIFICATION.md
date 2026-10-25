# Reproduction and verification (25 October 2026)

The source in this release is taken directly from the supplied original prototype archive. No replacement algorithm was produced.

## Synthetic lesson replay

```bash
PYTHONPATH=src python -m chartref.pipeline demo/assets/chart_lesson.mp4 demo/assets/chart_lesson.srt --out outputs/demo
python evaluate.py outputs/demo/references.json demo/assets/answer_key.json
```

Observed with Python 3.13.5, OpenCV 4.13.0 and NumPy 2.3.5:
- 2 slides detected, 72 bars (36 per slide).
- 16 spoken references considered; 12 labelled, 4 abstained.
- Precision 12/12; coverage 12/12; ambiguous moments abstained 4/4; no incorrect labels against this synthetic answer key.

## Unit tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

In the publication workspace, 13 tests passed and **1 could not run** (`test_approve_correct_export`): Flask was absent and package installation was blocked by network/DNS restrictions (`ModuleNotFoundError: No module named 'flask'`). This is an environment/dependency blocker, not proof that all 14 tests pass in this workspace. Install the declared dependencies and rerun all 14 tests. An earlier author-reported run of 14/14 is not independently reproduced here.

Synthetic evaluation does not establish accuracy on real trading-course recordings; false-label rates on unfamiliar footage remain unknown.

## GitHub Actions verification (25 October 2026)

The [successful CI run](https://github.com/AbdulkadirKhoujja/chart-reference-labeller/actions/runs/40235653721) for workflow commit `c1a79d71e4d735638db85a666eb2c2b5977d7895` ran the unchanged original suite on Python 3.13 under Ubuntu 24.04: **14 tests passed, zero failures or errors**. This supersedes the environment-only missing-Flask limitation for trading, but does not expand the claims about synthetic-only validation.
