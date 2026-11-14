# One-post trace — rehearse this from memory (Fix 10)

The interview question this answers: *"Take one post and walk me through
exactly how it becomes a prediction."* Use this real post, from the frozen
2026-11-14 run. Every number below is verifiable in the repo.

## The post

> **"$TENCENT (00700.HK)$ is this stock cursed haha"**
> Moomoo, 0700.HK (Tencent), post ID `117590929506314`
> https://www.moomoo.com/community/feed/tencent-00700-hk-is-this-stock-cursed-...

## 1. Timestamp — source time to UTC

The Moomoo feed page embeds a `DiscussionForumPosting` JSON-LD block with
`datePublished` in Hong Kong time (+08:00). The collector converts it to
UTC and stores it in `data/normalized/hk_posts.csv`:

- **2026-11-10T07:19:49Z** (UTC)

(Moomoo's own data sometimes carries hour 24, e.g. `2026-11-06T24:55:38+08:00`;
the collector treats that as midnight of the next day, not a parse failure.)

## 2. UTC to exchange-local time

07:19:49 UTC = **15:19:49 HKT** on 10 Nov (Asia/Hong_Kong, UTC+8).

## 3. Cutoff — which session does it belong to?

HKEX market cutoff is **16:10 HKT** (close 16:00 + closing auction).
15:19:49 is *before* the cutoff, so the post belongs to the **10 Nov
session** — it may inform the forecast for the *next* session (11 Nov).
A post at 16:30 HKT would belong to 11 Nov instead. (KRX cutoff is
15:40 KST, same rule.) The window for a session is
(previous session's cutoff, this session's cutoff].

## 4. Feature row

`reports/real_run/HKEX_features_daily_bar_history.csv`, row
**0700.HK / 2026-11-10**:

| Field | Value | Why |
| --- | --- | --- |
| post_count | 2 | this post + the "day 11: Morningstar" post from 09 Nov 21:39 HKT (after the 09 Nov cutoff, so it rolls into the 10 Nov window) |
| post_sentiment_mean | 0.50 | (1.0 + 0.0) / 2 |
| post_positive_share | 0.50 | 1 of 2 posts scored positive |
| post_negative_share | 0.00 | neither scored negative |
| close | 417.80 | Yahoo daily bar, 10 Nov |
| target_return | −0.0198 | log(409.60 / 417.80) — the 10 Nov → 11 Nov return this row predicts |
| next_date | 2026-11-11 | |

## 5. Label — what the scorer does with this post

`src/cwt_sentiment/sentiment.py`: keyword baseline, negation-aware.
"cursed" is **not in the lexicon**, so this post scores **0.0 — Neutral**,
even though a human reader (and the hand-labelled sample in
`tests/fixtures/labelled_sentiment_sample.csv`) calls it negative. Say
that out loud in the interview: it is the honest weakness of the scorer,
and it is why the labelled check reports Korean 9% / English 53% accuracy
and the sentiment feature stays exploratory-only. The other post in the
row ("Morningstar … undervalued") scores +1.0, which is where the row's
0.50 mean comes from.

## 6. Fold — where the row is tested

`reports/real_run/HKEX_experimental_sentiment_folds.csv`, **fold 2**:

- train 2026-11-04 → 2026-11-06 (targets end 2026-11-09)
- test **2026-11-10** — one date, 5 tickers
- the one-session purge means no training target overlaps a test feature
  date; folds are date-grouped, so no date appears in both train and test.

`reports/real_run/HKEX_experimental_sentiment_oos.csv`, row 0700.HK /
2026-11-10:

- predicted return **−0.0112** (predicted close 413.16)
- actual return **−0.0198** (actual close 409.60)
- direction correct (both negative); absolute error 0.0087.

## The one-sentence version

*"A Moomoo post published 15:19 Hong Kong time on 10 November falls
before the 16:10 cutoff, so it joins the 10 November feature row for
Tencent with one other post; the row's sentiment mean is 0.5, it sits in
fold 2 as a test row, and the model predicted −1.1% against an actual
−2.0% — right direction, and the post itself scored neutral because
'cursed' isn't in the keyword lexicon, which is exactly why I don't claim
the sentiment signal is validated."*
