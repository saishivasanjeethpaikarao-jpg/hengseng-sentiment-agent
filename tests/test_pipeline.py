import numpy as np
import pandas as pd
import pytest

from cwt_sentiment.collectors import normalize_social_rows, search_exa
from cwt_sentiment.cli import main
from cwt_sentiment.features import MODEL_FEATURES, aggregate_posts, build_training_frame
from cwt_sentiment.model import chronological_folds, evaluate_oos, forecast_latest
from cwt_sentiment.sentiment import score_sentiment


def test_baseline_sentiment_has_expected_signs():
    assert score_sentiment("bullish breakout") > 0
    assert score_sentiment("매수 호재 상승") > 0
    assert score_sentiment("看空 下跌") < 0
    assert score_sentiment("ordinary words") == 0


@pytest.mark.parametrize("text,expected", [
    # Review probe table: negation and sarcasm must not score +1.00 Bullish.
    ("not bullish at all", -1.0),
    ("bullish? yeah right, total scam", 0.0),
    ("상승하지 않다", -1.0),          # Korean: "not rising"
    ("不看多", -1.0),                # Chinese: "not bullish"
    ("利好 出货", 0.0),              # good news + distribution/dump
    ("never sell, strong buy", 1.0),  # one negation flips one term only
    ("don't buy this scam", -1.0),
    ("bullish, not really", -1.0),
    ("no gains here, total loss", -1.0),
    ("하락하지 않다", 1.0),          # Korean: "not falling"
    ("not a crash, it will rebound", 1.0),
])
def test_sentiment_negation_flips_the_modified_term(text, expected):
    assert score_sentiment(text) == pytest.approx(expected, abs=0.01)


def test_sentiment_compounds_count_once_not_per_character():
    # 上涨 must count once, not as 上涨 + 涨.
    assert score_sentiment("上涨") == pytest.approx(1.0)
    assert score_sentiment("涨停 大涨") == pytest.approx(1.0)
    assert score_sentiment("跌停 割肉") == pytest.approx(-1.0)


def test_sentiment_list_numbers_do_not_negate():
    assert score_sentiment("No. 5, buy the dip") > 0


def test_sentiment_cantonese_and_korean_retail_slang():
    assert score_sentiment("蟹貨 散水") < 0
    assert score_sentiment("떡상 가즈아") > 0
    assert score_sentiment("사기 조심") < 0
    assert score_sentiment("물렸다 손절") < 0


def test_actor_output_normalizes_to_canonical_schema():
    rows = normalize_social_rows(
        [{"created_at": "2026-10-01T08:30:00Z", "own_text": "看多", "like_count": 3, "views": "1.2K",
          "thread_url": "https://example.test/thread/1", "thread_id": "1"}],
        source="LIHKG", ticker="0700.HK",
    )
    assert rows.loc[0, "ticker"] == "0700.HK"
    assert rows.loc[0, "source"] == "LIHKG"
    assert rows.loc[0, "timestamp_utc"].endswith("+00:00")
    assert rows.loc[0, "text"] == "看多"
    assert rows.loc[0, "likes"] == 3
    assert rows.loc[0, "views"] == 1200
    assert pd.isna(rows.loc[0, "author_followers"])


def test_normalize_social_cli_writes_canonical_csv(tmp_path):
    raw_path = tmp_path / "raw.json"
    raw_path.write_text('[{"created_at":"2026-10-01T08:30:00Z","own_text":"positive"}]', encoding="utf-8")
    out_path = tmp_path / "normalized.csv"
    assert main([
        "normalize-social", "--raw", str(raw_path), "--source", "LIHKG",
        "--ticker", "0700.HK", "--out", str(out_path),
    ]) == 0
    posts = pd.read_csv(out_path)
    assert posts.loc[0, "ticker"] == "0700.HK"
    assert posts.loc[0, "source"] == "LIHKG"
    assert posts.loc[0, "text"] == "positive"


def test_exa_requires_free_only_confirmation_before_any_request():
    try:
        search_exa("Tencent stock news")
    except RuntimeError as exc:
        assert "free credits remain" in str(exc)
        assert "auto-recharge is off" in str(exc)
    else:
        raise AssertionError("Exa search must refuse without explicit free-only confirmation.")


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


def test_folds_purge_rows_whose_target_reaches_test_start():
    rows = []
    for day in range(1, 13):
        rows.append({"ticker": "A", "date": f"2026-01-{day:02d}",
                     "next_date": f"2026-01-{day + 1:02d}"})
    for train, test in chronological_folds(pd.DataFrame(rows), n_splits=3):
        assert train["next_date"].max() < test["date"].min()


def test_forecast_latest_rejects_labeled_latest_and_uses_only_prior_history():
    rows = []
    for day in range(1, 6):
        row = {feature: 0.0 for feature in MODEL_FEATURES}
        row.update({"ticker": "A", "date": f"2026-01-{day:02d}", "close": 100 + day,
                    "target_return": 0.01 if day < 5 else np.nan})
        rows.append(row)
    forecast = forecast_latest(pd.DataFrame(rows))
    assert forecast.loc[0, "date"] == "2026-01-05"
    rows[-1]["target_return"] = 0.01
    with pytest.raises(ValueError, match="in-sample"):
        forecast_latest(pd.DataFrame(rows))


def test_duplicate_posts_are_counted_once_and_missing_telemetry_is_not_observed_zero():
    posts = pd.DataFrame([
        {"ticker": "A", "source": "x", "post_id": "p1", "timestamp_utc": "2026-01-01T00:00:00Z", "text": "bullish"},
        {"ticker": "A", "source": "x", "post_id": "p1", "timestamp_utc": "2026-01-01T00:00:00Z", "text": "bullish"},
    ])
    grouped = aggregate_posts(posts, "UTC", "23:59")
    assert grouped.loc[0, "post_count"] == 1
    assert grouped.loc[0, "engagement_observed"] == 0
    assert grouped.loc[0, "followers_observed"] == 0
    assert "engagement_log" not in MODEL_FEATURES


def test_naive_event_timestamps_are_rejected():
    posts = pd.DataFrame([{"ticker": "A", "timestamp_utc": "2026-01-01 00:00:00", "text": "bullish"}])
    with pytest.raises(ValueError, match="explicit source timezone"):
        aggregate_posts(posts, "UTC", "23:59")
