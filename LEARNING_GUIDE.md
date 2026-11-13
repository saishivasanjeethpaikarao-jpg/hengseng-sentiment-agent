# Understand the project—and explain it confidently

You do not need to memorise every line. You need to understand the journey from a public post to a prediction, know how it was tested, and be honest about what is unfinished. Read [the actual results](RUN_RESULTS.md) alongside this guide.

## Your 60-second explanation

> “This is a research prototype for five Hong Kong and five Korean stocks. I collected timestamped public social posts, news headlines, and price history. I normalised them into tables, converted UTC timestamps to each exchange’s local time, and built features available at a stated cutoff. The target is the next trading session’s return. I tested a simple Ridge regression against a zero-return benchmark using expanding chronological splits, with a purge between training targets and test features. Under a zero-dollar constraint, I used explicitly labelled public-data substitutes rather than pretending that Apify and Exa had been used. The long-history price benchmark is tested; a reliable sentiment edge is not established.”

Then show the dashboard. Do not say the assignment is fully compliant: the source/tool gaps in `RUN_RESULTS.md` matter.

## 1. What each part means

**An API** is a structured way for one program to request data from another. **A scraper** extracts information from a public page. **An Apify Actor** is a program deployed on Apify; writing a local scraper is not the same as running an Actor. **Exa** is the news/search provider named in the assignment. Our free RSS news substitute is not Exa.

**A DataFrame** is a table in Python. A row might be one post or one stock on one trading day. A **feature** is an input to a model; the **target** is what we want to predict. A **baseline** is a simple comparison that the model should beat before we claim it adds value.

The pipeline is:

```text
Public pages / feeds / price endpoint
                ↓
Raw evidence + source status
                ↓
Canonical CSV tables
                ↓
UTC → local market time → cutoff/session alignment
                ↓
Daily features + next-session return labels
                ↓
Purged chronological validation against a baseline
                ↓
Human-readable report + clearly labelled forecasts
```

## 2. Find your way around the code

| File | What to understand |
|---|---|
| `config/assets.csv` | The ten tickers and their market/currency |
| `scripts/collect_*_public.py` and `collect_kr_feeds.py`, where present | Free public-data collection; inspect each script’s actual source and status |
| `src/cwt_sentiment/collectors.py` | Optional Apify/Exa adapters and normalisation; not evidence those services ran |
| `src/cwt_sentiment/sentiment.py` | Explainable keyword sentiment baseline |
| `src/cwt_sentiment/features.py` | Deduplication, timezone/cutoff alignment, daily aggregation, targets |
| `src/cwt_sentiment/model.py` | Purged date-grouped folds and guarded latest-row forecasts |
| `scripts/run_real_pipeline.py` | Offline real-data benchmark, provisional quote checks, report generation |
| `tests/` | Examples of behaviours the program must preserve |
| `data/normalized/` | Actual inputs in the downloadable data package; ignored by Git |
| `reports/real_run/` | Actual metrics, predictions, coverage, evidence, dashboard; ignored by Git |

Collection, analysis and reporting are separate on purpose. You can re-run the analysis offline without scraping or spending anything.

## 3. Trace one real example

The public Tencent Moomoo post titled **“$385 is great support for long term investment”** is linked in the collected data. Its structured publication timestamp is `2026-11-13T15:48:45+08:00`.

1. The collector retains the post URL, source, ID, text and timestamp.
2. It converts the timestamp to an unambiguous UTC representation.
3. The feature builder converts it back to `Asia/Hong_Kong` to apply the market rule.
4. At a `16:10` local cutoff, that `15:48` post is eligible for the November 13 feature row.
5. A post after `16:10` must not be inserted into that row. It rolls to the next supplied market session; if no future session is supplied, it is not used in the current forecast row.
6. The report can display the community’s `$385` support wording with its source. That does **not** establish a verified technical support level.

Latest Yahoo chart metadata also returned a Tencent quote of `386.6 HKD`, while the previous non-null daily close was approximately `398.8 HKD`. The current source daily close field was null. We therefore keep the quote snapshot separate and mark any quote-based calculation provisional. We do not invent a missing close.

Try this yourself:

```python
import numpy as np
previous_close = 398.8
provisional_quote = 386.6
print(np.log(provisional_quote / previous_close))
```

That calculation illustrates a return. It is not proof that our model predicted the move.

## 4. Understand the three input tables

A social row needs `ticker`, `source`, `timestamp_utc`, and `text`. Optional fields include `post_id`, `url`, `likes`, `reposts`, `views`, and `author_followers`.

A news row needs `ticker`, `published_at_utc`, and `title`. This run uses **headline-only** news; it is not full-article analysis.

A price row needs `ticker`, `date`, and `close`. The date is the **exchange-local trading date**, not a UTC date. Quotes have their own timestamped table because a quote and a completed daily close are not interchangeable.

Important distinctions:

- A reported `0 likes` is different from unavailable likes.
- No retained posts is different from no posts existing.
- A failed source is different from a successfully checked source with no matches.
- A thread title is different from a full post/reply thread.
- A stock-page sample is not an exhaustive ten-day archive.

Raw missing telemetry stays null. Aggregate numeric placeholders are accompanied by availability indicators. The coverage/status files are needed to interpret them correctly. Cumulative engagement and engagement-weighted sentiment are not retrospective model predictors: their values were observed at collection time, not necessarily at the old prediction cutoff.

## 5. What sentiment actually does

The keyword scorer uses small positive and negative vocabularies in English, Chinese and Korean. Its basic score is:

```text
(positive keyword hits − negative keyword hits) / total keyword hits
```

No recognised hits produces zero. A score at least `0.1` is labelled Bullish, at most `-0.1` Bearish, and otherwise Neutral. English terms are counted as unique matched words; Chinese/Korean terms use substring counts, which can overlap. These implementation choices are another reason to validate the scorer rather than assume it understands language.

This is multilingual **coverage**, not validated multilingual understanding. It can miss sarcasm, negation, Cantonese/Korean slang, context and quoted opinions. “Neutral” can simply mean “no vocabulary matched.” Do not call this a trained finance language model.

A sensible next step is to manually label a small source/language-balanced sample, compare the predictions with those labels, and inspect errors before adopting a more complex model.

## 6. What the model predicts

For each stock and session, the code calculates recent one-day/five-day returns and volatility, plus permitted social/news counts and sentiment aggregates.

The target is:

```python
target_return = np.log(next_session_close / current_close)
```

We predict a return rather than a price level because stock prices have very different scales. We recover a point price estimate with:

```python
predicted_price = current_price * np.exp(predicted_log_return)
```

Ridge is linear regression with a penalty that discourages excessively large coefficients. Here it is deliberately simple and fixed at `alpha=1`; no extensive hyperparameter search was performed.

The pipeline imputes missing model inputs numerically, standardises features, then fits Ridge. Those preprocessing steps are fitted **inside each training fold**, not on the entire dataset.

The long-history benchmark in the run report uses **price features only**. A two-year price history does not magically create two years of social history. A small sentiment experiment is attempted only if enough historical social feature dates actually exist, and remains exploratory even if its error looks lower.

## 7. How to tell whether it worked

Imagine training on older dates and testing on later ones. Then move forward and train on a larger past. That is expanding-window validation.

All stocks on one date stay in the same fold. Random row splitting would mix future information into the past. Because the target looks one session ahead, the final training rows are purged until:

```text
latest training target date < earliest test feature date
```

This is conservative. It prevents a test-period close from entering training labels at the boundary.

The zero-return benchmark predicts no change. **MAE** is the mean absolute error in predicted log return: lower is better. **Directional accuracy** asks how often the predicted sign matches the actual sign. Neither measure proves profitability after costs.

### Our actual result: the simple baseline won

| Market | Price-model MAE | No-change MAE | Model direction accuracy |
|---|---:|---:|---:|
| Hong Kong | 1.639% | **1.627%** | 47.5% |
| Korea | 2.707% | **2.695%** | 48.5% |

These are mean absolute **log-return** errors, not guaranteed price-error bands. Lower is better, so neither model beat no change. Do not say “the model was accurate” just because it produced a price.

The sentiment models also ran, but each had only **15 test rows across three dates**. Their MAEs were 4.563% (HKEX) and 4.502% (KRX), versus no-change errors of 1.927% and 2.581%. They improved on the equally tiny same-window price-only Ridge runs, but still lost to the simple baseline. That is not enough evidence that sentiment works. Keep these frozen results rather than repeatedly adjusting the model against the same test outcomes.

All five Korean stocks have both Naver and Daum records. Hong Kong has only 24 retained Moomoo posts across four stocks, no retained LIHKG posts, and no AIA social records. Every follower count is unavailable. These are collection limitations to explain—not zeros to hide or successful source integrations to claim.

Read three different outputs correctly:

1. **Historical OOS validation:** predictions on held-out historical dates with non-null daily close labels.
2. **Retrospective next-session quote check:** a past as-of prediction compared with a subsequently observed provisional quote. It was generated retrospectively, not recorded live before the move.
3. **New next-session forecast:** a point estimate based on the current provisional quote. Its future outcome is not yet known and cannot honestly be marked correct today.

Never describe the third as “evaluated” before that next session happens.

## 8. Run it yourself

From the downloaded project folder, create an environment and install dependencies.

**Windows PowerShell**

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev,public]'
pytest -q
python scripts/run_real_pipeline.py
```

**macOS/Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,public]'
pytest -q
python scripts/run_real_pipeline.py
```

Open `reports/real_run/dashboard.html`. The offline runner needs the real normalised CSVs included in the data package. A code-only GitHub clone does not contain those ignored data files.

Do not run Apify/Exa commands under this project’s zero-dollar restriction. A flag or API key does not prove that a call is free. Public collection scripts make network requests but do not use those paid APIs. Browser-based collectors may require `python -m playwright install chromium`; inspect the script and source availability first.

Useful commands for exploring the package:

```bash
cwt-sentiment --help
cwt-sentiment build --help
cwt-sentiment evaluate --help
cwt-sentiment forecast --help
```

`build` turns canonical data into features. `evaluate` runs the model’s chronological validation. `forecast` refuses a latest row that already has a label, preventing an in-sample result from being presented as a forecast. `report` creates the simpler market snapshot; the real-run script creates the richer integrated dashboard.

## 9. Interview questions you should be able to answer

**Why UTC?** One storage standard avoids ambiguous source clocks. The exchange-local cutoff is applied after conversion.

**Why not random train/test splitting?** It can train on the future and mix the same date across folds. Time-ordered date splits better reflect deployment.

**Why purge a session?** A training row’s next-session label can otherwise reach into the test boundary.

**Why a baseline?** A complicated model can look impressive while losing to “no change.” Compare identical test rows.

**Why not use every like/follower value?** They are cumulative values scraped now. Their historical as-of values are unknown; using them can leak future engagement into a backtest.

**Did you use Apify and Exa?** Not in this zero-cost run. The adapters exist, but local public collection/RSS were used and documented. Actual Actor IDs/run logs and an approved Exa route remain compliance gaps.

**Did sentiment improve predictions?** The tiny sentiment runs beat the same-window price-only Ridge runs but lost to no change, on only three test dates. That does not establish a durable edge. The longer price-only models also lost to no change.

**What would you improve first?** Source/tool compliance, longer timestamped social history, official-quality daily close data and calendar checks, a hand-labelled multilingual sentiment benchmark, then robust paired model tests. More complexity comes later.

**Is this a trading strategy?** No. There is no transaction-cost, slippage, liquidity, risk or portfolio validation.

**What did you personally learn/build?** Explain the parts you have actually read and reproduced. It is fine to say you used coding assistance. Do not claim an unverified model or source integration as your own completed achievement.

## 10. A practical learning exercise

1. Open one actual post row and locate its source URL.
2. Calculate its local time and decide which cutoff/session it belongs to.
3. Find the corresponding feature row.
4. Calculate one next-session log-return target by hand in Python.
5. Read one fold’s train end, target end and test start; verify the strict inequality.
6. Compare one prediction with zero return and the actual outcome.
7. Explain one missing source and one limitation without apologising or hiding them.

Because you use Codex, a useful prompt is: **“Explain `_local_events` line by line using one actual CSV row. Then help me add one cutoff test. Do not change the evaluation results or call any external API.”** Do this one module at a time. Being able to trace and test the pipeline is more valuable in an interview than memorising a polished pitch.
