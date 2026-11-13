# Live data access checklist

## Already prepared in this starter

The code can call Apify actors, normalize raw social output, query Exa, optionally download daily price bars, align UTC timestamps to supplied exchange sessions, build next-session labels, run chronological validation, and create an HTML report. Candidate universe and timezones are editable in `config/`.

## Source pairing required by the assignment

The proposed pairs are all on the assignment's list: LIHKG + AAStocks/ETNet for HKEX, and Naver Finance stock discussion boards + Daum Finance forums for KRX. The source-pair choice is not yet validated against live Apify actors. I found one [LIHKG Apify actor listing](https://apify.com/claude_code_reviewer/lihkg-scraper-en/api/python), which documents search/date filters but charges per scraped thread (listed from $2 per 1,000 threads). I did not find a verified Apify actor for the AAStocks/ETNet, Naver stock-board, or Daum forum sources in this pass. A [public Telegram actor listing](https://apify.com/george.the.developer/telegram-channel-scraper) is an assignment-approved alternative source, but it lists $5 per 1,000 messages and requires public channel names; it is not selected here. No paid actor has been run.

The Apify CLI defaults to a **$0.00 per-run charge cap** and at most 100 billable results. A source actor that charges for results will not run successfully with that cap; only raise it after deciding on a budget. The cap is enforced using Apify's run API parameter. Apify's [official run endpoint documentation](https://docs.apify.com/api/v2/actor-run-sync-get-dataset-items-post) describes `maxTotalChargeUsd` and `maxItems`.

## Needed before a real collection

1. **Apify access:** an API token and either existing, approved actor IDs/input files for two HK sources and two Korean sources, or approval to prepare/deploy custom Apify actors for the four listed sites. Verify each actor's input/output schema, source permissions, version, and price.
2. **Exa access:** an Exa API key. Its current [pricing page](https://exa.ai/pricing) lists $10 monthly starter credits and usage-based pricing after that; do not assume the account has unused credit. This code makes one search per asset and retrieves text, so confirm the account's limit before running it.
3. **Price source:** either the optional Yahoo Finance adapter after checking symbol coverage/terms, or provide a permitted provider's daily OHLCV CSV. Use 6–12 months of price history for validation while keeping the social scrape to the requested 10 days.
4. **Asset confirmation:** the ten symbols in `config/assets.csv` are editable examples, not specified by the assignment. Confirm them or replace them with five assets per exchange.

The saved-secret search found no Apify or Exa keys, and neither environment variable is available here. No external API call, paid actor run, or market scrape has been made. The credential values must be supplied through the secure form before any live calls; never place tokens in Git or ordinary email.

## Why no live results are included

Without the required credentials and four working source integrations, a full scrape cannot be performed honestly. This project does not fabricate posts, prices, forecasts, or performance results. First run a capped small test for each source, inspect missing timestamps, duplicate rate, ticker relevance and schema, then collect the 10-day window.
