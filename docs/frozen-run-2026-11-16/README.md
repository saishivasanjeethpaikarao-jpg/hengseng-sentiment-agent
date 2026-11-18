# Frozen run — 2026-11-16

The exact data behind the numbers in `reports/real_run/summary.json` for the
16 November 2026 run — the first run with the real Apify Actor and Exa search
(the 14 November run used local public collection and Google News RSS as
substitutes). Everything in this folder is a verbatim copy of what
`scripts/run_real_pipeline.py` read and wrote on that date; nothing here has
been edited since. `MANIFEST.sha256` lists the SHA-256 of every file in this
folder.

## What is in here

| Path | Contents |
| --- | --- |
| `data/hk_posts.csv` (30 rows) | HK social posts: Moomoo 23 (frozen 14 Nov), LIHKG 7 (3 frozen + 4 Apify) |
| `data/kr_posts.csv` (2,115 rows) | KR social posts: Naver 1,750, Daum 365 in the file (1,711 + 250 after the pipeline dedups overlapping collector/Apify rows; 1,990 posts total across both markets) |
| `data/prices.csv` (4,875 rows) | Yahoo daily bars, 10 tickers, 2024-11-18 → 2026-11-16 (2-year rolling window) |
| `data/quotes.csv` (10 rows) | Latest quotes, 2026-11-16 (all daily closes missing — provisional) |
| `data/news_public.csv` (188 rows) | RSS headlines (108, frozen 14 Nov) + Exa headlines (80) |
| `status/apify_run.json`, `status/apify_run_log.txt` | Apify Actor cwt-public-finance-sources (0jwqlJJLDge2NcQ1x), run nl0xo2ot0DVeCq2nu, SUCCEEDED 2026-11-16, 644 dataset rows |
| `status/exa_request_log.json` | Exa search: 10 queries (one per ticker), 80 headlines, last 10 days |
| `status/price_collection_status.json`, `status/quote_collection_status.json` | Yahoo prices/quotes refresh, 2026-11-16 |
| `reports/summary.json` | Evaluation summary (MAEs, folds, coverage) |
| `reports/next_session_forecasts.csv` | Next-session point forecasts (for Tue 2026-11-17; check only after that session's official close) |

## Frozen numbers (from `reports/summary.json`)

- HKEX price-only OOS MAE **1.638%** vs zero-return baseline **1.628%**,
  directional accuracy 47.1% (1,940 predictions, 388 dates).
- KRX price-only OOS MAE **2.719%** vs zero-return baseline **2.704%**,
  directional accuracy 48.1% (1,900 predictions, 380 dates).
- Sentiment experiment (30 rows, 6 dates — exploratory only): HKEX MAE
  9.45%, KRX MAE 10.76%; both lose to the zero-return baseline.

The price-only model does **not** beat the zero-return baseline. That is the
honest result; nothing was tuned to beat it.

## Cost

Apify run cost about **$0.05** (0.249 compute units; monthly usage $1.36 of the
$5 free credits). Exa spend is not measurable through its API.

## How to reproduce (from a clean clone)

```bash
pip install -e .[dev,public]
cp docs/frozen-run-2026-11-16/data/*.csv data/normalized/
python scripts/run_real_pipeline.py
```

Then compare `reports/real_run/summary.json` against
`docs/frozen-run-2026-11-16/reports/summary.json` — the price-only MAEs,
fold metrics and row counts must match exactly.

## Collection window and known limits

- Window: 2026-11-04 → 2026-11-16 (bounded latest-page samples; Apify
  10-day lookback).
- HKEX social is thin: 30 posts total. AIA (1299.HK) has **zero** retained
  social rows from either HK source; Meituan (3690.HK) has zero LIHKG rows.
  Moomoo returned **zero** posts in the Apify run (its 23 rows are from the
  14 November local collection).
- KRX is well covered (1,961 posts after dedup) but Naver is capped at 100
  posts per ticker by the Actor input.
- Quotes are provisional latest quotes, not official daily closes; the
  `next_session_forecasts.csv` forecasts are for the next session
  (Tuesday 2026-11-17) and must be checked only after that session's
  official close. The 14 November frozen forecasts (for Monday 2026-11-16)
  are checked separately by `scripts/check_next_session.py` after Monday's
  close — see `docs/prospective-check-2026-11-16.md`.
- The 14 November frozen package (`docs/frozen-run-2026-11-14/`) is kept
  untouched as the earlier baseline.
