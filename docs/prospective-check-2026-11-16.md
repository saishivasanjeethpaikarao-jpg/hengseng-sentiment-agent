# Prospective n+1 check — session Monday 2026-11-16 (Fix 7)

## What was frozen, and when

On 2026-11-14, `scripts/run_real_pipeline.py` wrote
`reports/real_run/next_session_forecasts.csv` from the 2026-11-13 close
(provisional latest quotes). A verbatim copy is frozen in
`docs/frozen-run-2026-11-14/reports/next_session_forecasts.csv` (SHA-256 in
`MANIFEST.sha256`). The forecasts were made **before** the next session
happened — that is what makes this check prospective rather than
retrospective.

Two models are frozen per ticker (10 tickers):

| Model | Basis |
| --- | --- |
| price-only benchmark | 2 years of daily bars; the primary, honest model |
| experimental short-window sentiment | tiny recent sample; no validated edge |

## The session date — calendar-verified

**Monday 16 November 2026 is a regular full trading session on both
exchanges.** Checked 2026-11-14 against the published 2026 calendars:

- **HKEX**: the official HKEX Stock Connect trading calendar lists
  November 2026 trading days as 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, **16**,
  17, 18, 19, 20, 23, 24, 25, 26, 27, 30 — 16 Nov is a trading day. The
  full 2026 HKEX closure list (1 Jan, 17–19 Feb, 3 Apr, 6–7 Apr, 1 May,
  25 May, 19 Jun, 1 Jul, 1 Oct, 19 Oct, 25 Dec) contains no November date.
  Regular hours 09:30–16:00 HKT; the repo's market cutoff is 16:10 HKT.
- **KRX**: 16 Nov 2026 is listed as a regular session 09:00–15:30 KST
  ("reopens on Monday 16 November 2026" after the weekend). The full 2026
  KRX closure list (1 Jan, 16–18 Feb, 2 Mar, 1 May, 5 May, 25 May, 3 Jun,
  17 Jul, 17 Aug, 24–25 Sep, 5 Oct, 9 Oct, 25 Dec, 31 Dec) contains no
  November closure. Note: 19 Nov is the CSAT exam day (delayed open
  10:00–16:30 KST) — a special timetable, not a closure, and not our
  session. The repo's market cutoff is 15:40 KST.

Sources: HKEX Stock Connect 2026 trading calendar (hkex.com.hk);
KRX 2026 holiday calendar via marketcalendars.com / isthemarketopen.com
(KRX official calendar as source).

## How to check (after the close)

```bash
python scripts/check_next_session.py
```

- Run only after both markets have closed on 2026-11-16 (HKEX 16:10 HKT,
  KRX 15:40 KST) and the daily bars are published on Yahoo — usually a
  few hours after the close. If a bar is not published yet, the script
  exits 2 and says so; **do not substitute a provisional quote**.
- It fetches the 2026-11-16 daily bar (official close) for each ticker
  from the Yahoo Finance chart API — the same endpoint the price
  collector uses — and writes
  `reports/prospective-check-2026-11-16.csv` with predicted vs actual
  close, realised log return, absolute error and direction per ticker
  and model.
- It prints MAE and direction accuracy per model.

## What this check can and cannot prove

- **Can**: whether the frozen forecasts were any good on one session, and
  — more importantly — that the forecast existed before the outcome.
- **Cannot**: prove or disprove a predictive edge. One session, 10
  tickers. The price-only model already loses to the zero-return baseline
  over 388/380 OOS dates; one good or bad day changes nothing. Report the
  result as it is, with the n=10 caveat, and do not cherry-pick the
  sentiment model if it happens to look better on this one day.
