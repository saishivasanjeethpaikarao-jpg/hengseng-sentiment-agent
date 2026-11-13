import numpy as np
import pandas as pd

from cwt_sentiment.collectors import normalize_social_rows
from cwt_sentiment.features import MODEL_FEATURES, aggregate_posts, build_training_frame
from cwt_sentiment.model import chronological_folds, evaluate_oos
from cwt_sentiment.sentiment import score_sentiment


def test_baseline_sentiment_has_expected_signs():
    assert score_sentiment("bullish breakout") > 0
    assert score_sentiment("매수 호재 상승") > 0
    assert score_sentiment("看空 下跌") < 0
    assert score_sentiment("ordinary words") == 0


def test_actor_output_normalizes_to_canonical_schema():
    rows = normalize_social_rows(
        [{"created_at": "2026-10-01T08:30:00Z", "own_text": "看多", "like_count": 3,
          "thread_url": "https://example.test/thread/1", "thread_id": "1"}],
        source="LIHKG", ticker="0700.HK",
    )
    assert rows.loc[0, "ticker"] == "0700.HK"
    assert rows.loc[0, "source"] == "LIHKG"
    assert rows.loc[0, "timestamp_utc"].endswith("+00:00")
    assert rows.loc[0, "text"] == "看多"
    assert rows.loc[0, "likes"] == 3


def test_utc_posts_map_to_local_time_and_roll_after_cutoff():
    posts = pd.DataFrame([
        {"ticker": "0700.HK", "timestamp_utc": "2026-10-01T07:30:00Z", "text": "bullish breakout", "likes": 3},
        # 16:30 Hong Kong time: after the 16:10 cutoff, so it rolls to the next session.
        {"ticker": "0700.HK", "timestamp_utc": "2026-10-01T08:30:00Z", "text": "bearish drop", "likes": 1},
        # Saturday: it maps to the next provided price session.
        {"ticker": "0700.HK", "timestamp_utc": "2026-10-03T04:00:00Z", "text": "bullish", "likes": 0},
    ])
    grouped = aggregate_posts(posts, "Asia/Hong_Kong", "16:10", session_dates=["2026-10-01", "2026-10-02", "2026-10-05"])
    day_one = grouped.loc[grouped["date"].eq("2026-10-01")].iloc[0]
    day_two = grouped.loc[grouped["date"].eq("2026-10-02")].iloc[0]
    day_three = grouped.loc[grouped["date"].eq("2026-10-05")].iloc[0]
    assert day_one["post_count"] == 1
    assert day_one["post_sentiment_mean"] > 0
    assert day_two["post_count"] == 1
    assert day_two["post_sentiment_mean"] < 0
    assert day_three["post_count"] == 1


def test_target_uses_next_row_per_ticker():
    prices = pd.DataFrame({
        "ticker": ["A", "A", "A"],
        "date": ["2026-01-05", "2026-01-06", "2026-01-07"],
        "close": [100.0, 110.0, 99.0],
    })
    empty_posts = pd.DataFrame(columns=["ticker", "timestamp_utc", "text"])
    empty_news = pd.DataFrame(columns=["ticker", "published_at_utc", "title", "text"])
    frame = build_training_frame(prices, empty_posts, empty_news, "Asia/Hong_Kong", "16:10")
    assert np.isclose(frame.loc[0, "target_return"], np.log(1.1))
    assert np.isclose(frame.loc[1, "target_return"], np.log(0.9))
    assert pd.isna(frame.loc[2, "target_return"])
    assert (frame["post_observed"] == 0).all()
    assert (frame["news_observed"] == 0).all()


def test_chronological_folds_keep_same_date_together():
    data = pd.DataFrame({
        "date": [f"2026-01-{day:02d}" for day in range(1, 9) for _ in range(2)],
        "ticker": ["A", "B"] * 8,
    })
    folds = list(chronological_folds(data, n_splits=3))
    for train, test in folds:
        assert set(train["date"]).isdisjoint(set(test["date"]))
        assert train["date"].max() < test["date"].min()
        assert len(test) % 2 == 0


def test_walk_forward_evaluator_returns_fold_predictions():
    rows = []
    for day in range(1, 25):
        for ticker_index, ticker in enumerate(["A", "B"]):
            row = {feature: 0.0 for feature in MODEL_FEATURES}
            row.update({
                "ticker": ticker,
                "date": f"2026-01-{day:02d}",
                "next_date": f"2026-01-{day + 1:02d}",
                "close": 100.0 + day + ticker_index,
                "target_close": 101.0 + day + ticker_index,
                "target_return": ((day % 4) - 1.5 + ticker_index * 0.2) / 100.0,
            })
            row["return_1d"] = day / 1000
            row["post_observed"] = day % 2
            rows.append(row)
    metrics, predictions = evaluate_oos(pd.DataFrame(rows), n_splits=3)
    assert len(metrics) == 3
    assert len(predictions) > 0
    assert predictions["predicted_close"].notna().all()
    assert (metrics["n_test"] > 0).all()
