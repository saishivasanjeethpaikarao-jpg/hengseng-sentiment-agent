# What the real-data run found

Collected **1,499 real public social records**, **110 news headlines**, **4,875 daily price bars**, and **10 latest quote snapshots** at **$0 external spend**. These are real records, not generated examples.

## The important caveat

**This is a working free-route research prototype, not a fully compliant assignment submission.** No Apify Actor was run; therefore there is no Actor ID or Actor run log. Exa was not used. Public local collection and Google News RSS are explicitly documented substitutes. The coverage table shows which source/ticker pairs actually yielded records; bounded samples are not exhaustive ten-day archives. Latest daily close fields are missing at the source; latest prices are separately labelled provisional quotes, not fabricated closes.

## What the validation says

The long-history experiment validates price features only. It uses a fixed Ridge model (alpha=1), pooled per market, and four expanding chronological folds with a conservative one-session target purge. No hyperparameters were selected after seeing the test results.

**The no-change baseline won in both markets.** Neither long-history price model established an edge; the tiny sentiment runs also lost to no change. Producing a point prediction is not evidence of predictive value.

All 1,499 author-follower counts are unavailable and remain null. Missing telemetry counts: {'likes': 11, 'reposts': 1499, 'views': 13, 'author_followers': 1499}. Naver/Daum naive site timestamps were explicitly interpreted as Asia/Seoul; source-clock accuracy was not independently certified.

### HKEX
Price-only OOS: **1,940 predictions across 388 dates** (2025-04-16–2026-11-11). MAE: **1.639% log return**; zero-return benchmark: **1.627%**; directional accuracy: **47.5%**.

Sentiment study: exploratory only; too few sessions for a reliable edge claim. Social observations cover 7 historical feature dates and 11 ticker-date rows. This is not enough to claim a durable edge.

Tiny paired experiment: 15 test rows across 3 dates; sentiment-feature MAE 4.563%, same-window price-only MAE 5.321%, zero-return MAE 1.927%. Treat as a demonstration, not a finding of predictive superiority.

### KRX
Price-only OOS: **1,900 predictions across 380 dates** (2025-04-18–2026-11-11). MAE: **2.707% log return**; zero-return benchmark: **2.695%**; directional accuracy: **48.5%**.

Sentiment study: exploratory only; too few sessions for a reliable edge claim. Social observations cover 7 historical feature dates and 20 ticker-date rows. This is not enough to claim a durable edge.

Tiny paired experiment: 15 test rows across 3 dates; sentiment-feature MAE 4.502%, same-window price-only MAE 4.903%, zero-return MAE 2.581%. Treat as a demonstration, not a finding of predictive superiority.

## Current forecast versus checked history

Yahoo daily bars with non-null source closes end on **2026-11-12**. The retrospective next-session check is in `reports/real_run/retrospective_next_session_quote_check.csv`; its outcomes are post-close quote snapshots, not confirmed daily closes. It is a retrospective holdout, not a live prediction made in advance.

`reports/real_run/next_session_forecasts.csv` contains new next-session point forecasts based on the current provisional quotes. Those future outcomes cannot be checked yet. The next session date has not been independently checked against an official holiday calendar. These are research outputs, not trading recommendations.

## Source coverage

| market   | ticker    | source        |   retained_records |
|:---------|:----------|:--------------|-------------------:|
| HKEX     | 0700.HK   | Moomoo        |                 10 |
| HKEX     | 0700.HK   | LIHKG         |                  0 |
| HKEX     | 9988.HK   | Moomoo        |                  8 |
| HKEX     | 9988.HK   | LIHKG         |                  0 |
| HKEX     | 0005.HK   | Moomoo        |                  2 |
| HKEX     | 0005.HK   | LIHKG         |                  0 |
| HKEX     | 3690.HK   | Moomoo        |                  4 |
| HKEX     | 3690.HK   | LIHKG         |                  0 |
| HKEX     | 1299.HK   | Moomoo        |                  0 |
| HKEX     | 1299.HK   | LIHKG         |                  0 |
| KRX      | 005930.KS | Naver Finance |                250 |
| KRX      | 005930.KS | Daum Finance  |                150 |
| KRX      | 000660.KS | Naver Finance |                250 |
| KRX      | 000660.KS | Daum Finance  |                 62 |
| KRX      | 035420.KS | Naver Finance |                250 |
| KRX      | 035420.KS | Daum Finance  |                  2 |
| KRX      | 035720.KS | Naver Finance |                250 |
| KRX      | 035720.KS | Daum Finance  |                  1 |
| KRX      | 005380.KS | Naver Finance |                250 |
| KRX      | 005380.KS | Daum Finance  |                 10 |

Zero means no retained records in this bounded collection, **not** proof that no discussions exist. Moomoo is a public linked-post sample. LIHKG records marked `thread_title_only` are titles, not complete reply threads. See the source status JSONs and row-level record types.

## Reproduce and learn

1. Install the package and optional public dependencies; run `pytest -q`.
2. Inspect `data/normalized/` and each collection-status JSON.
3. Run `python scripts/run_real_pipeline.py` to regenerate all analysis offline.
4. Open `reports/real_run/dashboard.html`, then inspect the CSV predictions against the raw inputs.
5. Read `LEARNING_GUIDE.md`; practice explaining cutoff timing, missingness, baseline comparison, and why the source substitutions matter.

## What remains before calling it submission-ready

Use tested Apify actors/custom actors with actual IDs and run logs if the evaluator requires them. Obtain an approved, verifiably free Exa allowance or an explicit evaluator-approved news substitution. Resolve any remaining source/ticker gaps and extend the bounded samples to genuine ten-day coverage. Collect a longer as-of social archive; label a multilingual sentiment sample; use official daily close data and a verified exchange calendar; re-run the same frozen evaluation. Do not hide these gaps in an interview.

Source links are retained in the collected CSV rows and provenance files. Relevant public surfaces: [LIHKG](https://lihkg.com/category/15), [Moomoo](https://www.moomoo.com/stock/00700-HK/community), [Naver](https://m.stock.naver.com/domestic/stock/005930/discussion), [Daum](https://m.finance.daum.net/quotes/A005930/talks), [Google News](https://news.google.com/), [Yahoo Finance chart](https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?range=1mo&interval=1d).
