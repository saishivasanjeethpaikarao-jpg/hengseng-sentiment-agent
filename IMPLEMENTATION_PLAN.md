# 5–7 day implementation plan

## Goal

Deliver a reproducible prototype for five HKEX and five KRX assets, using at least two assignment-listed social sources per market, recent Exa news, UTC-normalized events, exchange-local alignment, a ticker report, and next-session forecasts evaluated chronologically out of sample. Keep all collection within verified free usage; no paid actor, proxy, or Exa auto-recharge is allowed.

## Day 1 — Lock scope and prove free access

- Confirm or replace the ten example symbols in `config/assets.csv`; the assignment does not prescribe the exact assets.
- Test two public sources per exchange. Current candidates are LIHKG + Moomoo for HKEX and Naver Finance + Daum Finance for KRX, but the source-specific collectors are not verified. Find another assignment-listed source if one is inaccessible without paid usage.
- Apify's published Free plan includes $5/month in platform-usage credits. Check the account's remaining included allowance privately before any custom Actor build or run; no Store Actor or paid proxy may be used.
- Do not call Exa until the operator confirms in its dashboard that free credits remain and auto-recharge is disabled.
- The repository is public by the user's choice. Keep it code/templates only; do not commit API keys, scraped data, or personal account usage details.
- Confirm prediction cutoffs and the next-session target (recommended: next exchange session close-to-close return).

**Exit check:** the ten symbols are locked, source access is proven or a documented assignment-listed fallback is selected, and all cost gates remain at $0 out-of-pocket.

## Day 2 — Collect and normalize

- If the sources are accessible and free, collect the latest 10 days for five tickers per exchange. Capture UTC time, text, source, URL, and available engagement/author metadata; leave unavailable follower counts missing.
- Use Exa only after its free-balance and auto-recharge settings are verified. If not, document the blocker and do not make a request.
- Collect 6–12 months of permitted daily price bars for validation. The 10-day social window alone is insufficient for meaningful time-series validation.
- Keep raw outputs private and record source and schema versions.

**Exit check:** a coverage report shows rows, date span, missing timestamps, duplicates, and source counts per ticker/source; no paid service was used.

## Day 3 — Sentiment and ticker report

- Run the baseline scorer and manually inspect a stratified sample from each language/source. Prioritize Cantonese/Traditional Chinese and Korean; do not present an English-only lexicon as a validated multilingual model.
- Aggregate mentions, sentiment, engagement, and news by ticker and local trading date, respecting the chosen cutoff.
- Produce the first visual HTML report sorted by mentions and sentiment, with direction, current price, and reviewable position/support/resistance cues.

**Exit check:** the report renders and spot checks catch language, ticker-mapping, and timestamp errors.

## Day 4 — Predict and validate

- Define target `log(close[t+1] / close[t])`; use only information available by the chosen cutoff on day `t`.
- Compare a zero-return benchmark with a regularized model. Use expanding chronological folds, keep all tickers from each date together, and never shuffle.
- Report fold-level MAE, directional accuracy, baseline comparison, test periods, and asset coverage. Warn if folds or observations are too few.

**Exit check:** no leakage from future prices, posts, news, or preprocessing fitted on test periods.

## Day 5 — End-to-end run and reproducibility

- Run ingestion → normalization → feature build → validation → report only for sources that passed the free-access test.
- Check duplicates, timezone conversion, holidays, missing bars, ticker aliases, API errors, and source balance.
- Add tests for timestamp/cutoff handling, next-session labels, chronological splits, and report fields.
- Document exact Actor IDs only after actually creating and successfully testing a custom Actor; keep tokens out of the public README and ordinary email.

**Exit check:** a clean environment can reproduce the pipeline from documented inputs without spending money.

## Days 6–7 — Improve and submit

- Improve the weakest multilingual sentiment component using a small labeled evaluation set; report per-language/source checks.
- Tune only inside training windows. Add confidence/coverage indicators and avoid unsupported buy/sell claims.
- Freeze the run, remove secrets and unnecessary raw data, verify the public repository contains code/templates only, and provide the repository link plus honest limitations.
- Share any API token only through the recipient's approved secure process; never publish a live token or send it in ordinary email.

## Five-day compression

Combine Days 1–2, keep the model simple, and treat the final checks as a short Day 5 review. Do not cut source/coverage checks, timestamp validation, leakage controls, or the baseline comparison. If a source cannot be accessed without paid usage, document it and use an assignment-listed public alternative only after verifying that source's access path. Do not fabricate data or predictions.

## Assumptions and risks

The assignment implies Hong Kong and Korea markets and five assets per market, but does not fix the symbols. Current cutoffs are examples and need exchange-calendar verification. Social source pages may be dynamic or restrict automated access; candidate links do not prove an Apify collector exists. The baseline sentiment dictionary is illustrative, and position/support/resistance extractions are noisy community claims, not investment advice.
