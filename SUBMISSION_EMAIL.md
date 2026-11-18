# Submission email — DRAFT, DO NOT SEND

Send from Sai Shiva Sanjeeth Paikarao's email to **gilad@crowdwisdomtrading.com** only after Sai Shiva Sanjeeth Paikarao
approves the exact text. Do NOT paste live tokens in the email — offer them
through Gilad's secure process instead (last paragraph).

---

Subject: HengSeng sentiment agent — submission (repo + Apify/Exa evidence)

Hi Gilad,

Submitting the HengSeng exchange sentiment agent:

**Repo:** https://github.com/saishivasanjeethpaikarao-jpg/hengseng-sentiment-agent

**What it does:** a Python pipeline that collects public investor discussion
for 5 HKEX + 5 KRX tickers, scores sentiment with a negation-aware keyword
baseline, and forecasts the next session's log return with a leakage-aware
evaluation (4 expanding chronological folds, date-grouped, one-session
purge, zero-return baseline).

**Apify:** DONE — the custom Actor `cwt-public-finance-sources`
(ID `0jwqlJJLDge2NcQ1x`) ran on 2026-11-16, run `nl0xo2ot0DVeCq2nu`
(SUCCEEDED, 0.249 compute units, about $0.05 of the $5 free credits).
Run log in `data/apify/nl0xo2ot0DVeCq2nu/log.txt`, dataset 644 rows
(Naver 500, Daum 140, LIHKG 4, Moomoo 0).

**Exa:** DONE — the news pull ran on 2026-11-16
(`scripts/run_exa_news.py`, 10 queries, one per ticker): 80 headlines,
8 per ticker, last 10 days. Request/response log in `data/exa/`. The
14 November frozen run's Google News RSS headlines are retained alongside
and labelled as such.

**Frozen run (2026-11-16, $0.05 Apify spend):** 1,990 social posts,
188 headlines (108 RSS + 80 Exa), 4,875 daily bars. Reproducible from a
clean clone — see `docs/frozen-run-2026-11-16/` (data + status JSONs +
SHA-256 manifest). The 14 November run is kept in
`docs/frozen-run-2026-11-14/` as the earlier baseline. Results:
HKEX price-only MAE 1.638% vs zero-return 1.628% (1,940 rows, 388 dates);
KRX 2.719% vs 2.704% (1,900 rows, 380 dates). The price-only model does
not beat the zero-return baseline, and the sentiment pilot (30 rows, 6
dates) loses to it too — reported as-is, nothing tuned to beat it.

**Honest limitations (please read before judging the numbers):**
- HKEX social is thin: 30 posts total (LIHKG 7, Moomoo 23 from the
  14 November local collection — Moomoo returned zero in the Apify run).
  AIA (1299.HK) has zero retained social rows from either HK source. The
  10-day window is a bounded latest-page sample, not an archive.
- The sentiment scorer is a keyword baseline: hand-labelled check on 100
  real posts scores 24% overall (English 53%, Korean 9%) — it is not a
  validated signal and the pipeline labels it exploratory-only.
- Quotes are provisional latest quotes, not official closes. A genuinely
  prospective check was frozen for the next session (Mon 16 Nov 2026,
  calendar-verified on both exchanges) — see
  `docs/prospective-check-2026-11-16.md`. I ran
  `scripts/check_next_session.py` after that close against the official
  Yahoo daily bars: price-only MAE 2.172% with 6/10 directions right;
  experimental sentiment MAE 3.528%, also 6/10. One session, 10 tickers —
  that confirms nothing about an edge; it only shows the forecast was
  frozen before the outcome. The full per-ticker table is in
  `reports/prospective-check-2026-11-16.csv`.
- Engagement/follower fields are mostly missing (author followers
  unavailable for all 1,990 rows; reposts for all; likes for 12; views
  for 19); the pipeline records null, never zero.

**Apify/Exa tokens:** the Actor ID and run ID are above (IDs are not
secrets). The live API tokens I will share only through whatever secure
process you prefer — just tell me where to send them. I am not pasting
live tokens in email.

Thanks for the assignment — happy to walk through any of this live,
including the one-post trace (timestamp → UTC → local → cutoff → feature
row → label → fold) in `docs/trace-rehearsal.md`.

Best,
Sai Shiva Sanjeeth Paikarao
