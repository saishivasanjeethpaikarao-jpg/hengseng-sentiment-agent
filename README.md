# HKEX + KRX sentiment-to-price research prototype

A Python project for five Hong Kong and five Korean stocks: public social collection, headline news, daily prices, exchange-local feature alignment, next-session returns, purged chronological validation, provisional forecasts, and a visual report.

**This is a working free-route prototype, not a claim of full assignment compliance.** The assignment names Apify and Exa. No Apify Actor was run and no Exa query was made in this zero-dollar implementation. Local public collection and Google News RSS are documented substitutes. Source coverage is bounded and uneven; the actual coverage table—not the existence of an adapter—determines what was collected.

Start with **[RUN_RESULTS.md](RUN_RESULTS.md)** for actual counts, metrics and gaps, **[LEARNING_GUIDE.md](LEARNING_GUIDE.md)** to understand and explain the code, and **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** for the original 5–7 day work plan. [DATA_ACCESS.md](DATA_ACCESS.md) explains source boundaries.

## What is implemented

- Public Moomoo linked-post collection with structured publication timestamps; invalid source timestamps are rejected rather than guessed.
- Public LIHKG keyword search, newest-first finance-category title samples. Title-only records are marked as such; they are not complete reply threads.
- Naver’s observed public per-stock discussion feed with cursor pagination and news-item exclusion.
- Daum’s browser-observed debates feed, with collection success/failure recorded per ticker.
- Google News RSS headline-only collection as an **Exa substitute**.
- About two years of Yahoo daily bars and separately timestamped latest quote snapshots. Null source daily closes are not silently invented or forward-filled.
- Deduplication, explicit timezone validation, local cutoff/session alignment, multilingual keyword sentiment, next-session log-return labels.
- A price-only long-history benchmark, plus a guarded tiny sentiment experiment only where historical social coverage permits one. Four purged expanding folds keep dates together; preprocessing is fit on training folds only.
- CSV metrics/predictions/coverage/evidence and a self-contained HTML dashboard.

No claim of a profitable strategy or validated sentiment edge is made.

## Run the downloaded data package offline

The full downloadable project includes normalised data and generated reports. The public Git repository deliberately excludes collected text, raw pages, quote datasets and row-level reports.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,public]'
pytest -q
python scripts/run_real_pipeline.py
```

Open `reports/real_run/dashboard.html`. The analysis script makes **no network calls**. A code-only clone needs the normalised data from the data package before this command can run.

## Recollect using public free routes

These commands make public network requests, not Apify or Exa calls. Source availability and page schemas can change. Review the scripts and status files; do not bypass access controls or use paid proxies.

```bash
python scripts/collect_prices_public.py
python scripts/collect_quotes_public.py
python scripts/collect_news_public.py
python scripts/collect_kr_feeds.py
python scripts/collect_daum_public.py
python scripts/collect_hk_public.py
python scripts/run_real_pipeline.py
```

The Hong Kong collector needs Playwright Chromium. Install a local browser with `python -m playwright install chromium` if no supported system Chromium is present. Each collector saves provenance/status, retains only actual timestamps inside the requested window, and records its sampling cap. Re-running is not proof of exhaustive ten-day coverage.

## Key data schemas

| Table | Required fields |
|---|---|
| Social | `ticker, source, timestamp_utc, text` |
| News | `ticker, published_at_utc, title` |
| Daily prices | `ticker, date, close` |
| Latest quotes | `ticker, quote_timestamp_utc, quote_date_local, price` |

Optional social fields include `post_id,url,likes,reposts,views,author_followers,record_type,retrieved_at_utc`. Missing telemetry is not observed zero. Coverage/status files distinguish retained samples from failed or empty collections.

## Modeling rules worth checking

The target is `log(close[t+1] / close[t])`, where `t+1` is the next supplied trading session, not tomorrow’s calendar date. Events after a local cutoff roll to the next supplied session. HKEX uses `Asia/Hong_Kong`; KRX uses `Asia/Seoul`. The example cutoff/calendar choices need official verification before production use.

Training target dates must end strictly before the first test feature date. Latest-row forecasts must be unlabeled; an in-sample row is refused. Cumulative likes/views/followers and engagement-weighted sentiment are excluded from retrospective model predictors because their historical as-of values are unknown. The long-history result is **price-only**: two years of prices cannot substitute for two years of social observations.

The small keyword scorer does not reliably understand negation, slang, sarcasm or multilingual finance context. Support/resistance and position fields are unverified community wording cues, with reviewable evidence—not technical advice or actual portfolio holdings. Yahoo prices are third-party data, not certified official exchange closes; raw unadjusted prices may also need corporate-action checks.

## Optional API adapters—not used in this run

`cwt-sentiment --help` exposes `apify-pull`, `normalize-social`, `exa-pull`, `prices-pull`, `build`, `evaluate`, `forecast` and `report`. The generic Apify runner is not a source scraper, and a null Actor ID must not be invented. The Exa adapter requires an explicit free-balance/recharge confirmation; an API key or flag alone does not establish that a request is free. Do not run either provider under this project’s zero-dollar restriction without a verified no-charge route.

Keep API keys and `.env` out of Git. No credentials, account-specific billing details or collected public-user text are needed in the public repository. Data/report files remain in the private deliverable package.
