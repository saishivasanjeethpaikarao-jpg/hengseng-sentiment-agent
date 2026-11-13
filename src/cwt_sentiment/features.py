"""Event aggregation and next-session dataset construction."""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from .sentiment import score_sentiment

POST_FEATURES = [
    "post_count", "post_observed", "post_sentiment_mean", "post_sentiment_weighted",
    "post_positive_share", "post_negative_share", "engagement_total", "followers_mean",
]
NEWS_FEATURES = ["news_count", "news_observed", "news_sentiment_mean"]
MODEL_FEATURES = [
    "return_1d", "return_5d", "volatility_5d", "post_count_log", "post_observed",
    "post_sentiment_mean", "post_sentiment_weighted", "post_positive_share",
    "post_negative_share", "engagement_log", "news_count_log", "news_observed",
    "news_sentiment_mean",
]


def _local_events(frame: pd.DataFrame, timestamp_column: str, timezone: str, cutoff: str,
                  session_dates: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        out = frame.copy()
        out["session_date"] = pd.Series(dtype="object")
        return out
    out = frame.copy()
    ts = pd.to_datetime(out[timestamp_column], utc=True, errors="coerce")
    local = ts.dt.tz_convert(timezone)
    valid = ts.notna()
    out = out.loc[valid].copy()
    local = local.loc[valid]
    local_dates = local.dt.strftime("%Y-%m-%d")
    if session_dates is None:
        # Reporting can request 23:59 to count all captured events for each local date.
        out["session_date"] = local_dates.to_numpy()
        return out

    sessions = sorted(set(str(pd.Timestamp(d).date()) for d in session_dates))
    cutoff_time = time.fromisoformat(cutoff)
    session_set = set(sessions)
    assigned: list[str | None] = []
    for local_date, local_time in zip(local_dates.tolist(), local.dt.time.tolist()):
        if local_date in session_set and local_time <= cutoff_time:
            assigned.append(local_date)
            continue
        # After cutoff: use the next available session. Non-trading dates (weekends/holidays)
        # roll to the first available session on or after the local date.
        candidates = [s for s in sessions if s > local_date] if local_date in session_set else [s for s in sessions if s >= local_date]
        assigned.append(candidates[0] if candidates else None)
    out["session_date"] = assigned
    return out.dropna(subset=["session_date"])


def aggregate_posts(posts: pd.DataFrame, timezone: str, cutoff: str,
                    session_dates: list[str] | None = None) -> pd.DataFrame:
    """Aggregate canonical posts by ticker and exchange trading date.

    Inputs: ticker, timestamp_utc, text; optional likes/reposts/views/author_followers.
    When session_dates are supplied (recommended), events after cutoff or on non-trading days
    roll forward to the next available price session. Missing event coverage has explicit flags.
    """
    if posts.empty:
        return pd.DataFrame(columns=["ticker", "date", *POST_FEATURES])
    frame = posts.copy()
    for col in ["likes", "reposts", "views", "author_followers"]:
        if col not in frame:
            frame[col] = 0
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0).clip(lower=0)
    if "text" not in frame:
        frame["text"] = ""
    frame = _local_events(frame, "timestamp_utc", timezone, cutoff, session_dates)
    if frame.empty:
        return pd.DataFrame(columns=["ticker", "date", *POST_FEATURES])
    frame["sentiment"] = frame["text"].map(score_sentiment)
    frame["engagement"] = frame[["likes", "reposts", "views"]].sum(axis=1)
    frame["weight"] = 1.0 + np.log1p(frame["engagement"])
    frame["weighted_sentiment"] = frame["sentiment"] * frame["weight"]
    frame["positive"] = frame["sentiment"].gt(0).astype(float)
    frame["negative"] = frame["sentiment"].lt(0).astype(float)
    grouped = frame.groupby(["ticker", "session_date"], as_index=False).agg(
        post_count=("text", "size"),
        post_sentiment_mean=("sentiment", "mean"),
        weighted_sum=("weighted_sentiment", "sum"),
        weight_sum=("weight", "sum"),
        post_positive_share=("positive", "mean"),
        post_negative_share=("negative", "mean"),
        engagement_total=("engagement", "sum"),
        followers_mean=("author_followers", "mean"),
    )
    grouped["post_sentiment_weighted"] = grouped["weighted_sum"] / grouped["weight_sum"].replace(0, np.nan)
    grouped["post_sentiment_weighted"] = grouped["post_sentiment_weighted"].fillna(0)
    grouped["post_observed"] = 1
    grouped = grouped.rename(columns={"session_date": "date"})
    return grouped[["ticker", "date", *POST_FEATURES]]


def aggregate_news(news: pd.DataFrame, timezone: str, cutoff: str,
                   session_dates: list[str] | None = None) -> pd.DataFrame:
    """Aggregate canonical news records by ticker and exchange trading date."""
    if news.empty:
        return pd.DataFrame(columns=["ticker", "date", *NEWS_FEATURES])
    frame = news.copy()
    if "title" not in frame:
        frame["title"] = ""
    if "text" not in frame:
        frame["text"] = ""
    frame["combined_text"] = frame["title"].fillna("").astype(str) + " " + frame["text"].fillna("").astype(str)
    frame = _local_events(frame, "published_at_utc", timezone, cutoff, session_dates)
    if frame.empty:
        return pd.DataFrame(columns=["ticker", "date", *NEWS_FEATURES])
    frame["sentiment"] = frame["combined_text"].map(score_sentiment)
    grouped = frame.groupby(["ticker", "session_date"], as_index=False).agg(
        news_count=("combined_text", "size"),
        news_sentiment_mean=("sentiment", "mean"),
    )
    grouped["news_observed"] = 1
    return grouped.rename(columns={"session_date": "date"})


def build_training_frame(
    prices: pd.DataFrame,
    posts: pd.DataFrame,
    news: pd.DataFrame,
    timezone: str,
    cutoff: str,
    drop_unlabeled: bool = False,
) -> pd.DataFrame:
    """Create one row per asset/session; label with the next available close return."""
    required = {"ticker", "date", "close"}
    missing = required.difference(prices.columns)
    if missing:
        raise ValueError(f"prices missing required columns: {sorted(missing)}")
    bars = prices.copy()
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    bars["close"] = pd.to_numeric(bars["close"], errors="coerce")
    bars = bars.dropna(subset=["ticker", "date", "close"]).sort_values(["ticker", "date"])
    bars = bars.drop_duplicates(["ticker", "date"], keep="last")
    sessions = bars["date"].astype(str).unique().tolist()

    social = aggregate_posts(posts, timezone, cutoff, session_dates=sessions)
    headlines = aggregate_news(news, timezone, cutoff, session_dates=sessions)
    data = bars.merge(social, how="left", on=["ticker", "date"]).merge(headlines, how="left", on=["ticker", "date"])
    for col in POST_FEATURES + NEWS_FEATURES:
        if col not in data:
            data[col] = 0.0
        data[col] = pd.to_numeric(data[col], errors="coerce").fillna(0.0)

    data["return_1d"] = data.groupby("ticker")["close"].pct_change()
    data["return_5d"] = data.groupby("ticker")["close"].pct_change(5)
    data["volatility_5d"] = data.groupby("ticker")["return_1d"].transform(lambda s: s.rolling(5, min_periods=2).std())
    data["post_count_log"] = np.log1p(data["post_count"].clip(lower=0))
    data["engagement_log"] = np.log1p(data["engagement_total"].clip(lower=0))
    data["news_count_log"] = np.log1p(data["news_count"].clip(lower=0))
    next_close = data.groupby("ticker")["close"].shift(-1)
    data["target_return"] = np.log(next_close / data["close"])
    data["target_close"] = next_close
    data["next_date"] = data.groupby("ticker")["date"].shift(-1)
    data["target_return"] = data["target_return"].replace([np.inf, -np.inf], np.nan)
    if drop_unlabeled:
        data = data.dropna(subset=["target_return"])
    return data.reset_index(drop=True)
