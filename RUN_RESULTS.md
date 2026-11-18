# What the real-data run found

Collected **1,990 real public social records**, **188 news headlines**, **4,875 daily price bars**, and **10 latest quote snapshots** at **$0.05 Apify spend (Exa unmeasured)**. These are real records, not generated examples.

## The important caveat

**Apify and Exa runs completed on 2026-11-16.** Actor cwt-public-finance-sources (0jwqlJJLDge2NcQ1x), run nl0xo2ot0DVeCq2nu, returned 644 social records; Exa returned 80 headlines across 10 queries. Apify cost was about $0.05 of the $5 free credits; Exa spend is not measurable through its API. Public local collection (2026-11-14 frozen run) and Google News RSS headlines are retained alongside the new data and are explicitly documented. The coverage table shows which source/ticker pairs actually yielded records; bounded samples are not exhaustive ten-day archives. Latest daily close fields are missing at the source; latest prices are separately labelled provisional quotes, not fabricated closes. The frozen inputs for the 14 November run are shipped in `docs/frozen-run-2026-11-14/` with a SHA256 manifest, so those numbers reproduce from a clean clone.

## What the validation says

The long-history experiment validates price features only. It uses a fixed Ridge model (alpha=1), pooled per market, and four expanding chronological folds with a conservative one-session target purge. No hyperparameters were selected after seeing the test results.

**The no-change baseline won in both markets.** Neither long-history price model established an edge; the tiny sentiment runs also lost to no change. Producing a point prediction is not evidence of predictive value.

All 1,990 author-follower counts are unavailable and remain null. Missing telemetry counts: {'likes': 12, 'reposts': 1990, 'views': 19, 'author_followers': 1990}. Naver/Daum naive site timestamps were explicitly interpreted as Asia/Seoul; source-clock accuracy was not independently certified.

### HKEX
Price-only OOS: **1,940 predictions across 388 dates** (2025-04-22–2026-11-13). MAE: **1.638% log return**; zero-return benchmark: **1.628%**; directional accuracy: **47.1%**.

Sentiment study: exploratory only; too few sessions for a reliable edge claim. Social observations cover 9 historical feature dates and 15 ticker-date rows. This is not enough to claim a durable edge.

Tiny paired experiment: 30 test rows across 6 dates; sentiment-feature MAE 9.452%, same-window price-only MAE 10.796%, zero-return MAE 1.922%. Treat as a demonstration, not a finding of predictive superiority.

### KRX
Price-only OOS: **1,900 predictions across 380 dates** (2025-04-22–2026-11-13). MAE: **2.719% log return**; zero-return benchmark: **2.704%**; directional accuracy: **48.1%**.

Sentiment study: exploratory only; too few sessions for a reliable edge claim. Social observations cover 9 historical feature dates and 29 ticker-date rows. This is not enough to claim a durable edge.

Tiny paired experiment: 30 test rows across 6 dates; sentiment-feature MAE 10.758%, same-window price-only MAE 8.779%, zero-return MAE 2.353%. Treat as a demonstration, not a finding of predictive superiority.

## Current forecast versus checked history

Yahoo daily bars with non-null source closes end on **2026-11-16**. The retrospective next-session check is in `reports/real_run/retrospective_next_session_quote_check.csv`; its outcomes are post-close quote snapshots, not confirmed daily closes. It is a retrospective holdout, not a live prediction made in advance.

`reports/real_run/next_session_forecasts.csv` contains new next-session point forecasts based on the current provisional quotes. Those future outcomes cannot be checked yet. The next session date has not been independently checked against an official holiday calendar. These are research outputs, not trading recommendations.

## Source coverage

| market   | ticker    | source        |   retained_records |
|:---------|:----------|:--------------|-------------------:|
| HKEX     | 0700.HK   | Moomoo        |                  9 |
| HKEX     | 0700.HK   | LIHKG         |                  1 |
| HKEX     | 9988.HK   | Moomoo        |                  8 |
| HKEX     | 9988.HK   | LIHKG         |                  3 |
| HKEX     | 0005.HK   | Moomoo        |                  2 |
| HKEX     | 0005.HK   | LIHKG         |                  2 |
| HKEX     | 3690.HK   | Moomoo        |                  4 |
| HKEX     | 3690.HK   | LIHKG         |                  0 |
| HKEX     | 1299.HK   | Moomoo        |                  0 |
| HKEX     | 1299.HK   | LIHKG         |                  0 |
| KRX      | 005930.KS | Naver Finance |                350 |
| KRX      | 005930.KS | Daum Finance  |                167 |
| KRX      | 000660.KS | Naver Finance |                350 |
| KRX      | 000660.KS | Daum Finance  |                 70 |
| KRX      | 035420.KS | Naver Finance |                350 |
| KRX      | 035420.KS | Daum Finance  |                  2 |
| KRX      | 035720.KS | Naver Finance |                311 |
| KRX      | 035720.KS | Daum Finance  |                  1 |
| KRX      | 005380.KS | Naver Finance |                350 |
| KRX      | 005380.KS | Daum Finance  |                 10 |

Zero means no retained records in this bounded collection, **not** proof that no discussions exist. Moomoo is a public linked-post sample. LIHKG records marked `thread_title_only` are titles, not complete reply threads. See the source status JSONs and row-level record types.

## Reproduce and learn

1. Install the package and optional public dependencies; run `pytest -q`.
2. Inspect `data/normalized/` and each collection-status JSON.
3. Run `python scripts/run_real_pipeline.py` to regenerate all analysis offline.
4. Open `reports/real_run/dashboard.html`, then inspect the CSV predictions against the raw inputs.
5. Read `LEARNING_GUIDE.md`; practice explaining cutoff timing, missingness, baseline comparison, and why the source substitutions matter.

## What remains before calling it submission-ready

Apify and Exa runs are done (Actor 0jwqlJJLDge2NcQ1x, run nl0xo2ot0DVeCq2nu, 2026-11-16; Exa 10 queries, 80 headlines; request logs in data/apify/nl0xo2ot0DVeCq2nu/ and data/exa/exa_request_log.json). What remains: resolve the HKEX social gap (4 Apify posts; Moomoo returned zero), extend the bounded samples to genuine ten-day coverage, collect a longer as-of social archive, use official daily close data and a verified exchange calendar, and re-run the same frozen evaluation. Do not hide these gaps in an interview.

Source links are retained in the collected CSV rows and provenance files. Relevant public surfaces: [LIHKG](https://lihkg.com/category/15), [Moomoo](https://www.moomoo.com/stock/00700-HK/community), [Naver](https://m.stock.naver.com/domestic/stock/005930/discussion), [Daum](https://m.finance.daum.net/quotes/A005930/talks), [Google News](https://news.google.com/), [Yahoo Finance chart](https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?range=1mo&interval=1d).
