# Interview-day cheat sheet

## 60-second pitch

“I built a Python research prototype for five Hong Kong and five Korean stocks. It collects public discussion, headlines and daily prices, normalizes records, aligns timestamps to each exchange’s local cutoff, and creates next-session return labels. I tested a Ridge model with expanding chronological folds and a one-session target purge, then compared it with predicting zero return. Ridge did not beat that no-change benchmark in either market. The sentiment experiment is tiny and does not establish an edge. Under the $0 limit, I used clearly labelled public-source and RSS substitutes rather than claiming to have used Apify or Exa. My next steps are provider compliance through a verified no-charge path, fuller Hong Kong coverage, and a manually checked multilingual sentiment benchmark.”

## Numbers to know

| Result | Ridge MAE | No-change MAE | Takeaway |
|---|---:|---:|---|
| HKEX price-only | 1.639% | **1.627%** | No-change slightly better; 1,940 predictions / 388 dates |
| KRX price-only | 2.707% | **2.695%** | No-change slightly better; 1,900 predictions / 380 dates |
| HKEX sentiment | 4.563% | **1.927%** | Only 15 rows over 3 dates; exploratory |
| KRX sentiment | 4.502% | **2.581%** | Only 15 rows over 3 dates; exploratory |

Lower mean absolute log-return error (MAE) is better. There is no demonstrated profitable strategy.

## Data and gaps

- 1,501 social records: 1,475 Korean and 26 Hong Kong (23 Moomoo + 3 LIHKG); 108 RSS headlines; 4,875 daily price bars; 10 latest-quote snapshots.
- Korea: Naver has 250 rows per asset; Daum counts are 150, 62, 10, 2 and 1.
- Hong Kong: Moomoo has 23 total; LIHKG retained 3 (only 0005.HK and 9988.HK covered); AIA has no retained social sample.
- Author-follower counts are unavailable for all 1,501 rows. Do not describe missing values as zero.
- The source pulls are bounded latest-page samples, not exhaustive historical archives. Latest quote forecasts have not yet been evaluated — a genuinely prospective check is frozen for Mon 16 Nov 2026 (see `docs/prospective-check-2026-11-16.md`).
- No Apify Actor run or Exa query has happened yet. The Actor is built and locally tested (`apify-actor/`), the Exa pull is scripted (`scripts/run_exa_news.py`); both are blocked on Shiv's keys. Local public collectors and RSS are substitutes, not completed provider integrations.

## Leakage answer

“I split chronologically by date and keep all assets from a date together. I purge the boundary so a training row’s next-session target cannot cross into test time. Imputation and scaling are fit inside each training fold only. I also exclude retrospective cumulative engagement values when their historic as-of values are unknown.”

## What I would do next

1. Satisfy the provider/source requirements only with a verified $0 path.
2. Improve Hong Kong coverage and collect genuinely historical, as-of social snapshots.
3. Verify exchange calendars, cutoffs and official closes.
4. Annotate a balanced multilingual sentiment sample and evaluate by source/language.
5. Repeat the same frozen date-based evaluation; never tune on the final test period.

## Do not claim

Do not claim profitability, validated sentiment lift, complete coverage, use of Apify/Exa, official exchange closes, or that a forecast was correct. Be truthful about coding assistance and demonstrate the modules you personally understand.

For the diagrams, interactive practice quiz and expandable answers, open [INTERVIEW_STUDY_PACK.html](INTERVIEW_STUDY_PACK.html).