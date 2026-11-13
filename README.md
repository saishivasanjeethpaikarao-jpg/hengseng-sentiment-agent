# HKEX + KRX Sentiment-to-Price Starter

A reproducible Python starter for the assignment. It supports Apify scraping (generic actor runner), Exa news, optional daily price bars, exchange-local alignment, a visual ticker report, and chronological out-of-sample next-session evaluation. It is a working scaffold, not a finished live run: no scraped data or model performance is claimed here.

## What the assignment asks for

In plain terms, build one pipeline for two markets: choose five assets on Hong Kong Exchange (HKEX) and five on Korea Exchange (KRX); scrape the latest 10 days of social posts from at least two different listed sources per exchange using Apify; collect recent asset news with Exa; align event timestamps with market prices; summarize each ticker's sentiment, direction, position cues, and support/resistance mentions; make a visual report ranked by mentions/sentiment; and predict the next session's price with honest out-of-sample validation. The work is due within one week and the submission asks for a repository link plus the actual API/actor details used.

## Source choices and unresolved access

`config/sources.json` proposes sources from the assignment's own list: LIHKG + AAStocks/ETNet in Hong Kong and Naver Finance + Daum Finance in Korea. These are source choices, not verified Apify actors. One public [LIHKG Apify listing](https://apify.com/claude_code_reviewer/lihkg-scraper-en/api/python) charges per scraped thread; one public [Telegram actor listing](https://apify.com/george.the.developer/telegram-channel-scraper) charges per message and requires channel names. Do not start a paid actor without approving its price. If no suitable existing actor is available for an assignment-listed source, a custom Apify actor may be required after verifying permitted access and Apify account costs. Actor IDs and input schemas belong in the run manifest once actually used—never guess them.

The API adapter reads `APIFY_API_TOKEN` and `EXA_API_KEY` from environment variables. They are not in the repository. The Apify runner defaults to a **$0.00 maximum charge per run** and caps paid-result actors at 100 items; raise the cap only after approving a budget. Exa's current pricing page lists monthly starter credits but usage can become paid; check account credit before calls.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\\Scripts\\activate
pip install -e '.[dev,prices]'
cp .env.example .env            # add credentials locally; never commit .env
```

Run `cwt-sentiment --help` to see commands and options.

### 1. Collect the sources

For each selected actor, save the exact input JSON that matches that actor's documented schema and run:

```bash
cwt-sentiment apify-pull --actor-id 'owner~actor' --input path/to/actor_input.json --out data/raw/source.json
cwt-sentiment normalize-social --raw data/raw/source.json --source LIHKG --ticker 0700.HK --out data/normalized/lihkg_0700.csv
```

The first command has `--max-total-charge-usd 0` by default, so an actor needing paid usage stops rather than spending. Only supply a larger `--max-total-charge-usd` after approving that amount. Repeat for every chosen source/asset. Use `--field-map mapping.json` if actor output field names differ from the default aliases. `config/apify_input.json` is an example schema for the candidate LIHKG actor only; it is not universal and does not indicate that its paid actor has been approved.

Fetch Exa news after checking available account credit:

```bash
cwt-sentiment exa-pull --assets config/assets.csv --market HKEX --days 10 --out data/normalized/hk_news.csv
```

Optional price history convenience adapter (the assignment does not prescribe a market-data provider; verify access/terms or replace with an approved provider):

```bash
cwt-sentiment prices-pull --assets config/assets.csv --market HKEX --period 1y --out data/normalized/hk_prices.csv
```

Collect at least 6–12 months of daily bars for a useful time-series validation. The 10-day requirement is for social collection; ten price observations alone cannot support credible validation.

### 2. Build aligned features and evaluate

Run separately for each market so the correct timezone/cutoff is used:

```bash
cwt-sentiment build --posts data/normalized/hk_posts.csv --news data/normalized/hk_news.csv --prices data/normalized/hk_prices.csv --timezone Asia/Hong_Kong --cutoff 16:10 --out data/features/hk.csv
cwt-sentiment evaluate --features data/features/hk.csv --splits 4 --metrics-out reports/hk_metrics.csv --predictions-out reports/hk_predictions.csv
cwt-sentiment forecast --features data/features/hk.csv --out reports/hk_forecast.csv
```

For Korea, use `Asia/Seoul` and a confirmed cutoff. The target is next available session's log return `log(close[t+1] / close[t])`; the prediction is also expressed as an estimated next close. Expanding chronological folds split by unique date so all assets from a date stay together; a zero-return benchmark is included. No random shuffle is used.

### 3. Create the visual report

```bash
cwt-sentiment report --posts data/normalized/hk_posts.csv --prices data/normalized/hk_prices.csv --assets config/assets.csv --market HKEX --timezone Asia/Hong_Kong --out reports/hk.html
```

The report sorts by mentions and sentiment and includes current price, sentiment/direction, and heuristic position/support/resistance cues. Review those text extractions before relying on them.

## Canonical input schemas

All event timestamps should be UTC ISO-8601 strings; retain original timestamps separately when available. `posts.csv` requires `ticker,source,timestamp_utc,text`; optional: `likes,reposts,views,author_followers,post_id,url`. `news.csv` requires `ticker,published_at_utc,title`; optional: `text,url,source`. `prices.csv` requires `ticker,date,close`; optional: `open,high,low,volume,currency,data_source`. Price `date` must be the exchange-local trading date (`YYYY-MM-DD`).

The Apify pull keeps raw actor JSON. `normalize-social` maps common LIHKG/Telegram fields to the canonical schema, but source-specific mappings still need inspection. The exact output fields can change by actor version, so save raw responses and actor IDs for reproducibility.

## Time alignment and validation limits

Event timestamps are parsed as UTC then assigned to a local date/session from the supplied price dates. Events after the configured local cutoff and events on non-trading dates roll forward to the next available price session; events after the final supplied price date cannot be aligned. For production, use an exchange calendar that includes official holidays/half-days and verify the prediction cutoff against market hours. The cutoff is an example default, not an exchange guarantee.

The current target is next available close-to-close return. Price-only history longer than 10 days helps validate code but does not create historical social sentiment. Stronger validation needs historical sentiment/news features too. The baseline sentiment dictionary is a demonstrator, not a validated Cantonese/Korean finance model; label a sample from each source/language and report errors before making claims. Missing-event flags distinguish no coverage from neutral sentiment.

## Security and responsible use

Keep `.env` private and never commit API keys, tokens, authorization URLs, or raw private-group content. The assignment asks for actual provider/actor details; actor IDs are fine to list, but do not send a live API token through public Git or ordinary email. Share a key only through a secure method approved by the recipient. Collect public, permitted content only; honor source terms, actor terms, rate limits, privacy expectations, and data retention rules. All sentiment/position/support/resistance outputs are noisy community claims, not investment advice.

## Tests

```bash
pytest
```

Tests use small in-memory fixtures only to check code behavior; they are not collected market data or evidence of predictive performance.
