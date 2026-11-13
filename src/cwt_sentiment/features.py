"""Event aggregation and next-session dataset construction."""

from __future__ import annotations

from datetime import time

import numpy as np
import pandas as pd

from .sentiment import score_sentiment

POST_FEATURES = [
    "post_count", "post_observed", "post_sentiment_mean", "post_sentiment_weighted",
    "post_positive_share", "post_negative_share", "engagement_total", "engagement_observed",
    "followers_mean", "followers_observed",
]
NEWS_FEATURES = ["news_count", "news_observed", "news_sentiment_mean"]
MODEL_FEATURES = [
    "return_1d", "return_5d", "volatility_5d", "post_count_log", "post_observed",
    "post_sentiment_mean", "post_positive_share",
    "post_negative_share", "news_count_log",
    "news_observed", "news_sentiment_mean",
]


def _local_events(frame: pd.DataFrame, timestamp_column: str, timezone: str, cutoff: str,
                  session_dates: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        out = frame.copy()
        out["session_date"] = pd.Series(dtype="object")
        return out
    out = frame.copy()
    parsed = []
    for value in out[timestamp_column].tolist():
        if pd.isna(value):
            parsed.append(pd.NaT)
            continue
        try:
            stamp = pd.Timestamp(value)
        except (TypeError, ValueError):
            parsed.append(pd.NaT)
            continue
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError(f"{timestamp_column} contains a naive timestamp; explicit source timezone required")
        parsed.append(stamp.tz_convert("UTC"))
    ts = pd.Series(parsed, index=out.index)
    local = ts.dt.tz_convert(timezone)
    valid = ts.notna()
    out = out.loc[valid].copy()
    local = local.loc[valid]
    local_dates = local.dt.strftime("%Y-%m-%d")
    if session_dates is None:
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
        candidates = [s for s in sessions if s > local_date] if local_date in session_set else [s for s in sessions if s >= local_date]
        assigned.append(candidates[0] if candidates else None)
    out["session_date"] = assigned
    return out.dropna(subset=["session_date"])


def deduplicate_events(frame: pd.DataFrame, timestamp_column: str) -> pd.DataFrame:
    """Remove collector retries while retaining distinct same-text events."""
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    keys = []
    for _, row in out.iterrows():
        ticker = str(row.get("ticker", ""))
        source = str(row.get("source", ""))
        identifier = next((row.get(col) for col in ("post_id", "article_id", "news_id")
                           if pd.notna(row.get(col)) and str(row.get(col)).strip()), None)
        if identifier is not None:
            key = ("id", ticker, source, str(identifier).strip())
        else:
            url = row.get("url", row.get("post_url", row.get("article_url", "")))
            text = row.get("text", row.get("title", ""))
            url_text = "" if pd.isna(url) else str(url).strip()
            content_text = "" if pd.isna(text) else " ".join(str(text).split())
            key = ("content", ticker, source, url_text, content_text,
                   str(row.get(timestamp_column, "")).strip())
        keys.append(key)
    return out.loc[~pd.Series(keys, index=out.index).duplicated(keep="first")].copy()


def aggregate_posts(posts: pd.DataFrame, timezone: str, cutoff: str,
                    session_dates: list[str] | None = None) -> pd.DataFrame:
    """Aggregate canonical posts by ticker and exchange trading date."""
    if posts.empty:
        return pd.DataFrame(columns=["ticker", "date", *POST_FEATURES])
    frame = deduplicate_events(posts, "timestamp_utc")
    for col in ["likes", "reposts", "views"]:
        if col not in frame:
            frame[col] = np.nan
        frame[col] = pd.to_numeric(frame[col], errors="coerce").clip(lower=0)
    if "author_followers" not in frame:
        frame["author_followers"] = np.nan
    frame["author_followers"] = pd.to_numeric(frame["author_followers"], errors="coerce").clip(lower=0)
    frame["engagement_observed"] = frame[["likes", "reposts", "views"]].notna().any(axis=1).astype(int)
    frame["followers_observed"] = frame["author_followers"].notna().astype(int)
    for col in ["likes", "reposts", "views"]:
        frame[col] = frame[col].fillna(0)
    frame["author_followers"] = frame["author_followers"].fillna(0)
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
        post_count=("text", "size"), post_sentiment_mean=("sentiment", "mean"),
        weighted_sum=("weighted_sentiment", "sum"), weight_sum=("weight", "sum"),
        post_positive_share=("positive", "mean"), post_negative_share=("negative", "mean"),
        engagement_total=("engagement", "sum"), engagement_observed=("engagement_observed", "max"),
        followers_mean=("author_followers", "mean"), followers_observed=("followers_observed", "max"),
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
    frame = deduplicate_events(news, "published_at_utc")
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
        news_count=("combined_text", "size"), news_sentiment_mean=("sentiment", "mean"),
    )
    grouped["news_observed"] = 1
    return grouped.rename(columns={"session_date": "date"})


def build_training_frame(prices: pd.DataFrame, posts: pd.DataFrame, news: pd.DataFrame,
                         timezone: str, cutoff: str, drop_unlabeled: bool = False) -> pd.DataFrame:
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
