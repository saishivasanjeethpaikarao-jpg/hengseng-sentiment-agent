# Submission email — DRAFT, DO NOT SEND

Send from Shiv's email to **gilad@crowdwisdomtrading.com** when the items
marked ⏳ below are resolved (or when Shiv decides to submit with the
limitations stated). Do NOT paste live tokens in the email — offer them
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

**Apify:** ⏳ PENDING — the custom Actor is built and its fetch logic is
tested against the real public endpoints
(`apify-actor/` in the repo; local test 2026-11-14), but no run has happened
yet because the run needs my Apify API token. [Once run, replace this line
with: Actor ID `<id>`, run ID `<id>`, run log in
`data/apify/<run_id>/log.txt`, dataset `<n>` rows.]

**Exa:** ⏳ PENDING — the news pull is scripted and key-gated
(`scripts/run_exa_news.py`, 10 queries, one per ticker) but not yet called,
because it needs my Exa API key. News in the current frozen run is Google
News RSS, labelled as the substitute. [Once called, replace this line with:
Exa request/response log in `data/exa/`, `<n>` results.]

**Frozen run (2026-11-14, $0 spend):** 1,501 social posts, 108 RSS
headlines, 4,875 daily bars. Reproducible from a clean clone — see
`docs/frozen-run-2026-11-14/` (data + status JSONs + SHA-256 manifest) and
`python scripts/verify_frozen_run.py --reproduce`. Results:
HKEX price-only MAE 1.639% vs zero-return 1.627% (1,940 rows, 388 dates);
KRX 2.707% vs 2.695% (1,900 rows, 380 dates). The price-only model does
not beat the zero-return baseline, and the sentiment pilot (15 rows, 3
dates) loses to it too — reported as-is, nothing tuned to beat it.

**Honest limitations (please read before judging the numbers):**
- HKEX source #2 (LIHKG) returned only 3 rows; AIA (1299.HK) has zero
  retained social rows from either HK source. The 10-day window is a
  bounded latest-page sample, not an archive.
- The sentiment scorer is a keyword baseline: hand-labelled check on 100
  real posts scores 24% overall (English 53%, Korean 9%) — it is not a
  validated signal and the pipeline labels it exploratory-only.
- Quotes are provisional latest quotes, not official closes. A genuinely
  prospective check is frozen for the next session (Mon 16 Nov 2026,
  calendar-verified on both exchanges) — see
  `docs/prospective-check-2026-11-16.md`; I will run
  `scripts/check_next_session.py` after that close and share the result.
- Engagement/follower fields are missing for 1,499/1,499 social rows in
  the original collection (the sources do not expose them); the pipeline
  records null, never zero.

**Apify/Exa tokens:** I will share the Actor ID, run ID and Exa
confirmation through whatever secure process you prefer — just tell me
where to send them. I am not pasting live tokens in email.

Thanks for the assignment — happy to walk through any of this live,
including the one-post trace (timestamp → UTC → local → cutoff → feature
row → label → fold) in `docs/trace-rehearsal.md`.

Best,
Sai Shiva Sanjeeth Paikarao
