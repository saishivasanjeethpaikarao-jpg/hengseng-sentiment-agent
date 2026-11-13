# Data access: what worked and what it proves

The real-run outputs and source-status JSON files are authoritative. A reachable page does not prove a complete scraper; an implemented API adapter does not prove that provider was used.

## Public routes used or observed

| Source | Verified route | Important limitation |
|---|---|---|
| Moomoo | Rendered stock community page → linked public post HTML → `DiscussionForumPosting.datePublished` | Bounded latest-post sample; some source timestamps are malformed and rejected. Not a complete ten-day archive. |
| LIHKG | Public browser keyword search → observed `/api_v2/thread/search` response; newest-first finance subjects | Current records are explicitly title-only, not full reply threads. Per-ticker matches can be absent. |
| Naver Finance | Public `/front-api/discussion/list` with `discussionType=domesticStock`, `itemCode`, page size and observed `lastOffset` cursor | Five-page cap per ticker; busy boards may cover only hours. `isNews` items are excluded from social posts. |
| Daum Finance | Public mobile page observed `/api/home/daum?path=/content/debates/A{code}?page=...&perPage=30&notice=true` | See actual collection status for which ticker calls succeeded; do not infer coverage from the route alone. |
| Google News RSS | Public keyword headline feed with actual `pubDate` timestamps | Headline-only **Exa substitute**; uneven company coverage and aggregator links. |
| Yahoo Finance | Public chart daily bars and separate chart-metadata latest quotes | Third-party source; current daily close fields can be null. Latest quotes are provisional, not silently substituted as official closes. |

Public entry pages: [LIHKG](https://lihkg.com/category/15), [Moomoo](https://www.moomoo.com/stock/00700-HK/community), [Naver](https://m.stock.naver.com/domestic/stock/005930/discussion), [Daum](https://m.finance.daum.net/quotes/A005930/talks), [Google News](https://news.google.com/), [Yahoo chart](https://query1.finance.yahoo.com/v8/finance/chart/0700.HK?range=1mo&interval=1d).

## Required-tool gap

**No Apify Actor was created, built or run for this collection. Actor IDs remain null.** The source-specific local scripts are not Apify execution evidence. If the evaluator requires Apify, deploy/test appropriate custom actors only after a verified no-charge route is available, retain actual IDs and logs, and rerun collection.

**No Exa request was made.** RSS news is clearly labelled as a replacement, not passed off as Exa output. Obtain evaluator acceptance of the substitute or a verified, authorised free Exa allowance before calling the requirement complete.

The external data-provider spend cap is **USD 0**. No paid Store Actor, paid proxy, subscription, auto-recharge setting change or paid API call was authorised. A provider’s advertised free tier is not evidence of the current account’s remaining allowance. Account-specific balances and credentials are not included in this public project.

## Files to inspect in the full data package

- `data/normalized/hk_collection_status.json`
- `data/normalized/kr_collection_status.json`
- `data/normalized/daum_collection_status.json`, where produced
- `data/normalized/news_collection_status.json`
- `data/normalized/price_collection_status.json`
- `data/normalized/quote_collection_status.json`
- `reports/real_run/coverage.csv` and `summary.json`

Source IDs, URLs, timestamps, retrieval metadata and field availability accompany actual records. Null means unavailable; zero retained rows does not mean no discussions exist. Raw evidence stays outside the public Git repository.

## Before submission

Resolve every missing required source/ticker pair, expand bounded sampling to true ten-day coverage, distinguish full text from titles, verify official exchange calendars/cutoffs and daily-close quality, and collect a much longer as-of social history before claiming a predictive sentiment edge. Document any evaluator-approved substitution explicitly rather than hiding it.
