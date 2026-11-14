# Frozen run — 2026-11-14

The exact data behind the numbers in `RUN_RESULTS.md` and `README.md` for the
14 November 2026 run. Everything in this folder is a verbatim copy of what
`scripts/run_real_pipeline.py` read and wrote on that date; nothing here has
been edited since. `MANIFEST.sha256` lists the SHA-256 of every file in this
folder — verify it with `python scripts/verify_frozen_run.py`.

## What is in here

| Path | Contents |
| --- | --- |
| `data/hk_posts.csv` (26 rows) | HK social posts: Moomoo 23, LIHKG 3 |
| `data/kr_posts.csv` (1,475 rows) | KR social posts: Naver 1,250, Daum 225 |
| `data/prices.csv` (4,875 rows) | Yahoo daily bars, 10 tickers, 2024-11-14 → 2026-11-12 |
| `data/quotes.csv` (10 rows) | Latest quotes, 2026-11-13 (all daily closes missing) |
| `data/news_public.csv` (108 rows) | RSS headlines, last 10 days |
| `status/*.json` | Per-source collection status + provenance (attempted / retained / errors) |
| `reports/summary.json` | Frozen evaluation summary (MAEs, folds, coverage) |
| `reports/next_session_forecasts.csv` | Frozen next-session point forecasts (see Fix 7 note below) |

## Frozen numbers (from `reports/summary.json`)

- HKEX price-only OOS MAE **1.639%** vs zero-return baseline **1.627%**,
  directional accuracy 47.5% (1,940 predictions, 388 dates).
- KRX price-only OOS MAE **2.707%** vs zero-return baseline **2.695%**,
  directional accuracy 48.5% (1,900 predictions, 380 dates).
- Sentiment experiment (15 rows, 3 dates — exploratory only): HKEX MAE
  6.66%, KRX MAE 4.78%; both lose to the zero-return baseline.

The price-only model does **not** beat the zero-return baseline. That is the
honest result; nothing was tuned to beat it.

## How to reproduce (from a clean clone)

```bash
pip install -e .[dev,public]
cp docs/frozen-run-2026-11-14/data/*.csv data/normalized/
python scripts/run_real_pipeline.py
python scripts/render_readme_mae_chart.py
```

Then compare `reports/real_run/summary.json` against
`docs/frozen-run-2026-11-14/reports/summary.json` — the price-only MAEs,
fold metrics and row counts must match exactly. The automated version of
this check is:

```bash
python scripts/verify_frozen_run.py --reproduce
```

It verifies the manifest, copies the repo to a temp dir, restores the frozen
data there, re-runs the pipeline, and diffs the MAEs. (It needs the same
Python environment the repo was installed in; it does not touch your working
`data/` or `reports/` folders.)

## Collection window and known limits

- Window: 2026-11-04 → 2026-11-13 (10 days, bounded latest-page samples).
- HKEX source #2 (LIHKG) returned only 3 rows; AIA (1299.HK) has **zero**
  retained social rows from either HK source. See
  `status/hk_collection_status.json` and `RESEARCH_NOTES.md`.
- No Apify run and no Exa call were part of this run (no keys available);
  news is the RSS substitute. See `SUBMISSION_EMAIL.md`.
- Quotes are provisional latest quotes, not official daily closes; the
  `next_session_forecasts.csv` forecasts are for the next session
  (Monday 2026-11-16, calendar-checked — see
  `docs/prospective-check-2026-11-16.md`) and must be checked only after
  that session's official close.
