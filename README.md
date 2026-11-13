# HKEX + KRX Sentiment-to-Price Starter

A reproducible Python scaffold for the assignment: source adapters, multilingual baseline sentiment, exchange-local event alignment, next-session targets, chronological validation, and an HTML ticker report. It is not a completed live run: no social dataset, Exa results, forecasts, or model-performance claims are included.

## Assignment requirements

Choose five assets on HKEX and five on KRX; collect the latest 10 days of social posts from at least two listed sources per exchange; gather related news using Exa; align posts and news with market sessions; report sentiment, direction, position cues, and support/resistance mentions; then forecast the next session and validate chronologically out of sample. The assignment requests a repository link and provider/actor details, not API tokens in a public repository.

## Source candidates and current access status

The tentative Hong Kong pair is **LIHKG + Moomoo Community**. LIHKG's public category listing links to a finance section, but asset-keyword retrieval has not been tested. Moomoo's public ticker page displays ticker-tagged posts through a rendered-page extraction; a direct HTTP request returned only a generic empty app document, so a browser-based collector still needs testing. Neither source has a verified Apify Actor ID.

The tentative Korea pair is **Naver Finance discussions + Daum Finance talks**. Naver's public hot feed contains stock-tagged posts, but its per-stock page is client-loaded and a stable ticker-feed endpoint has not been verified. Daum's public per-stock talks page exposes posts, but the page is dynamic and still needs a tested collector. Source details and links are in `RESEARCH_NOTES.md` and `DATA_ACCESS.md`.

These are assignment-listed candidates, not proven collectors. Do not claim source coverage until an actual, free-only test returns relevant records with timestamps. The generic Apify client is a runner, not a source scraper; `config/apify_input.json` is a custom-Actor template and is not valid input for a third-party actor.

## Free-only safeguards

Apify's published Free plan is $0/month with $5 in monthly platform-usage credits; no account-specific balance or billing status is included here. No third-party Store Actor, Actor build/run, paid proxy, or social scrape has been used. Custom Actor runs consume the Free plan's monthly usage credits, so recheck the remaining allowance in the account dashboard before any run; never use a paid Actor or paid proxy. The Apify CLI's `--max-total-charge-usd` defaults to `$0.00`, which blocks billable runs unless a deliberate cap is provided.

Exa has not been called. Its Free tier and optional auto-recharge depend on the user's account settings; this project cannot verify the remaining balance or recharge setting using the supplied standard API key. The `exa-pull` command is now blocked unless the operator explicitly confirms in the Exa dashboard that free credits remain and auto-recharge is off. Never pass that confirmation flag otherwise.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e '.[dev,prices]'
cp .env.example .env            # add credentials locally; never commit .env
pytest
```

Run `cwt-sentiment --help` to see commands and options.

### Social collection

Only use a source-specific Actor after its public-source access, input/output schema, and zero-cost path are confirmed. The generic runner retains raw output and has a `$0.00` charge cap by default:

```bash
cwt-sentiment apify-pull --actor-id 'owner~your-custom-actor' --input config/apify_input.json --out data/raw/source.json
cwt-sentiment normalize-social --raw data/raw/source.json --source LIHKG --ticker 0700.HK --out data/normalized/lihkg_0700.csv
```

The example input is not runnable until a custom Actor implementing that template exists. A positive Apify run cap may consume included Free-plan credits; only use one after checking the account still has enough free allowance and confirming no paid Actor/proxy is involved.

### Exa news

The connector is included, but the project refuses to call it without this explicit dashboard check:

```bash
cwt-sentiment exa-pull --assets config/assets.csv --market HKEX --days 10 --out data/normalized/hk_news.csv \
  --confirm-exa-free-balance-and-auto-recharge-off
```

Use the flag only after confirming both conditions in Exa's dashboard. If the account status is uncertain, leave the step disabled.

### Optional daily prices

The assignment does not specify a price provider. The starter includes an optional Yahoo Finance adapter; check availability and terms or replace it with an approved provider. For useful validation, collect 6–12 months of daily bars; the 10-day social window is not enough by itself.

```bash
cwt-sentiment prices-pull --assets config/assets.csv --market HKEX --period 1y --out data/normalized/hk_prices.csv
```

### Build, evaluate, forecast, and report

Run separately for each market so its timezone and prediction cutoff are correct:

```bash
cwt-sentiment build --posts data/normalized/hk_posts.csv --news data/normalized/hk_news.csv --prices data/normalized/hk_prices.csv --timezone Asia/Hong_Kong --cutoff 16:10 --out data/features/hk.csv
cwt-sentiment evaluate --features data/features/hk.csv --splits 4 --metrics-out reports/hk_metrics.csv --predictions-out reports/hk_predictions.csv
cwt-sentiment forecast --features data/features/hk.csv --out reports/hk_forecast.csv
cwt-sentiment report --posts data/normalized/hk_posts.csv --prices data/normalized/hk_prices.csv --assets config/assets.csv --market HKEX --timezone Asia/Hong_Kong --out reports/hk.html
```

For Korea, use `Asia/Seoul` and a confirmed cutoff. The target is the next available session's log return, `log(close[t+1] / close[t])`; expanding chronological folds split by date, so all assets from a date stay together. A zero-return benchmark is included; no random shuffle is used.

## Canonical schemas

Social rows use `ticker,source,timestamp_utc,text` and optionally `likes,reposts,views,author_followers,post_id,url`. News rows use `ticker,published_at_utc,title` and optionally `text,url,source`. Price rows use `ticker,date,close` and optionally `open,high,low,volume,currency,data_source`. Timestamps should be stored in UTC ISO-8601 form; price dates should be exchange-local trading dates.

## Limits and safety

Events after the configured local cutoff and events on non-trading dates roll to the next available supplied market session. Use an official exchange calendar for production. The baseline keyword scorer is a demonstrator, not a validated Cantonese/Korean finance model; label a sample from each source/language before reporting conclusions. Position, support, and resistance phrases are noisy community claims, not investment advice. Missing follower counts must remain missing rather than be invented.

Keep `.env`, API keys, raw data, and private/closed-group content out of Git. Do not email API tokens in ordinary email; share them only through the recipient's approved secure process. The assignment repository is public by the user's choice, so include code and templates only.
