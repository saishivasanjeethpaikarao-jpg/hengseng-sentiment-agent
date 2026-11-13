# Live data access checklist

## Prepared in the starter

The code can run a selected Apify Actor with a default `$0.00` charge cap, normalize common social-post fields, query Exa after an explicit free-only confirmation, optionally fetch daily prices, align UTC events to supplied exchange sessions, build next-session labels, run chronological validation, and create an HTML report.

No social scrape, Exa query, Actor creation/build/run, or live market-price pull has been performed. There are no live datasets, forecasts, or performance metrics in the repository.

## Source access status

The assignment requires two different listed social sources per exchange. The current candidates are **LIHKG + Moomoo Community** for HKEX and **Naver Finance discussions + Daum Finance talks** for KRX. These pairs are not yet proven end-to-end collectors, and no Actor IDs are set.

| Source | What is verified | What still needs a free-only test |
|---|---|---|
| LIHKG | The public category listing shows a finance section and recent threads. | Confirm ticker/keyword search and thread/post fields through a custom public-page collector. |
| Moomoo Community | A rendered public page extraction shows ticker-tagged posts. | A direct HTTP response was only an empty app document; test a browser-rendered path without a paid proxy. |
| Naver Finance | The public hot discussion feed contains stock-tagged posts. | The per-stock discussion page is client-loaded; identify/verify the unauthenticated post-feed path. |
| Daum Finance | A public per-stock talks page exposes a ticker-specific post list. | Verify the dynamic list can be collected repeatably using a free custom collector. |

AAStocks' tested forum URL returned page-not-found, and the ETNet quote page tested did not expose user-post discussions. A public Telegram finance channel was also checked, but the visible messages were mainly macro/gold commentary rather than a dependable five-HK-ticker feed. These are not selected as working source paths. See `RESEARCH_NOTES.md` for public URLs and source-level detail.

## Free-only boundary

Apify's published Free plan is $0/month with $5 in monthly platform-usage credits. That does not make every Actor or proxy free: custom Actor builds/runs consume included monthly usage credits, and no Store Actor or paid proxy may be used. Verify the account's remaining allowance in its dashboard before any custom run and keep the run cap within the included allowance. The generic runner's default cap is `$0.00`.

The user's Exa key is available only through the secure environment, not in Git. No Exa request has been made because the supplied standard API key does not reveal the account's remaining free credits or auto-recharge state. Before using Exa, the operator must confirm in the Exa dashboard that free credits remain and auto-recharge is disabled, then pass `--confirm-exa-free-balance-and-auto-recharge-off` to the CLI. If either setting is uncertain, do not call Exa.

## Remaining implementation steps

1. Verify that the two chosen sources per exchange can each return recent, relevant, public posts and required metadata without paid Actors or proxies. If a source is blocked, pick another assignment-listed source only after verifying its access path; do not substitute a paid source.
2. Check the Apify Free account's remaining allowance before building or running any custom Actor. Save its exact Actor ID, source URLs, input schema, and version after a successful test; do not invent IDs.
3. Confirm Exa's free balance and auto-recharge setting in its dashboard before using the Exa adapter.
4. Confirm or replace the example asset universe in `config/assets.csv`, and verify exchange cutoffs/calendars.
5. Collect 6–12 months of price history from a permitted source for validation; keep social posts to the requested 10-day window.

The ten tickers in `config/assets.csv` are editable examples, not assignment-prescribed assets. API tokens must never be committed to the public repository or sent by ordinary email. Keep raw outputs private until retention and source terms are checked.
