# 5–7 day implementation plan

## Goal
Deliver a reproducible prototype for the assignment: five Hong Kong-listed assets and five Korea-listed assets; at least two social sources per market via Apify; recent Exa news; UTC-normalized events aligned to exchange-local trading dates; a ticker-level visual report; and next-session price forecasts evaluated chronologically out of sample.

## Day 1 — Lock scope and prove data access
- Confirm the 10-symbol universe and whether the reviewer accepts the proposed source pairs: LIHKG + AAStocks/ETNet for Hong Kong, and Naver Finance + Daum Finance for Korea.
- Identify one usable Apify actor per source, verify its output fields and that the source/actor permits the intended collection. Record actor IDs and a small sample response. Start all API access immediately; source-access delays are the largest schedule risk.
- Create the private Git repository, `.env` setup, canonical CSV schemas, and a short README. Never commit API tokens or raw private/closed-group content.
- Decide prediction cutoff times and the exact next-session target (recommended: next exchange session close-to-close return).

**Exit check:** all four source paths are technically viable, or a documented fallback is selected; canonical schema is fixed.

## Day 2 — Collect and normalize
- Scrape the most recent 10 days for five tickers per exchange, capturing UTC timestamp, text, source, engagement, and author follower count when available.
- Pull recent ticker-relevant Exa results with title, publication timestamp, URL, and text/snippet.
- Collect substantially more price history than 10 days (target 6–12 months of daily bars) for validation. The 10-day social window is not enough to support a credible time-series test by itself.
- Normalize timestamps to UTC at ingestion; retain the original timestamp and source. Map each post/news item to the relevant exchange-local date only in feature construction.

**Exit check:** coverage report shows rows, date span, missing timestamps, and source counts for each ticker/source.

## Day 3 — Sentiment and ticker report
- Implement a baseline scorer, then manually inspect a stratified sample from each language/source. Prioritize Traditional Chinese/Cantonese and Korean performance; do not present an English-only lexicon as a validated multilingual model.
- Aggregate mention counts, sentiment, engagement, and news features by ticker and local trading date, respecting a clear prediction-time cutoff.
- Produce the first visual HTML report sorted by mentions and sentiment, with direction, current price, and reviewable position/support/resistance cues.

**Exit check:** report renders; spot checks catch obvious language, ticker-mapping, and timestamp errors.

## Day 4 — Predict and validate
- Define target `log(close[t+1] / close[t])`; add only information available by the chosen cutoff on day `t`.
- Compare a simple zero-return baseline with a regularized model. Use expanding-window/chronological folds; never shuffle rows or split randomly. Keep all tickers from a date in the same fold.
- Report fold-level MAE, directional accuracy, baseline comparison, test periods, and asset coverage. Add a warning if folds or observations are too few.

**Exit check:** no leakage from next-session prices, future posts/news, or preprocessing fit on test periods.

## Day 5 — End-to-end run and reproducibility
- Run ingestion → normalization → feature build → validation → visual report on the full dataset.
- Check duplicates, timezone conversion, market holidays, missing bars, ticker alias collisions, API errors, and source balance.
- Add tests for timestamp/cutoff handling, next-session labels, chronological splits, and report fields.
- Write setup, run commands, limitations, and exact actor IDs/API providers in the repository (tokens remain private).

**Exit check:** a clean environment can reproduce the pipeline from documented inputs and environment variables.

## Day 6 — Improve the weakest part (optional but recommended)
- Improve the multilingual sentiment approach using a validated model or a small manually labeled evaluation set; report per-language/source checks.
- Tune only inside the training window or keep the model intentionally simple. Add confidence/coverage indicators and avoid unsupported buy/sell claims.
- Re-run and compare with the baseline; keep changes only if out-of-sample results are defensible.

## Day 7 — Final review and submission
- Freeze the run, remove secrets and unnecessary raw data, verify repository access, and include a concise report plus limitations.
- Confirm the requested submission email, repository link, and actor IDs. Share API tokens only through the recipient's approved secure process; do not publish them in Git or a normal README.
- Submit before the stated deadline and retain the exact commit/run artifacts.

## Five-day compression
If only five days are available, combine Days 1–2, keep the model simple, and treat Days 6–7 as short final checks on Days 4–5. Do not cut timestamp validation, leakage controls, source coverage checks, or the baseline comparison. If any source cannot be accessed quickly, state the blocker and use an assignment-approved public alternative rather than fabricating data.

## Assumptions and risks to resolve early
- The assignment implies two exchanges (Hong Kong and Korea) and five assets in each; the exact tickers are not specified.
- The proposed four communities are candidates, not guaranteed Apify actors. Actor availability, output schemas, language coverage, access rules, and API permissions must be confirmed on Day 1.
- Last-10-day posts are for current sentiment/reporting; price history should be longer for out-of-sample validation.
- “Position” and support/resistance are noisy text extractions, not investment advice. Show source snippets or confidence and label them as community claims.
- This is an engineering submission, not a promise of a hiring outcome; prioritize clear evidence, honest limitations, and reproducibility.
