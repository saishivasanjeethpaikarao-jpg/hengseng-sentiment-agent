"""Support/resistance and market-cutoff tests; no network requests or credentials."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from cwt_sentiment.levels import community_levels
from cwt_sentiment.report import _levels, _report_rows

pytest.importorskip("matplotlib")
spec = importlib.util.spec_from_file_location(
    "real_pipeline", Path(__file__).parents[1] / "scripts" / "run_real_pipeline.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_report_levels_require_money_not_ambiguous_numbers():
    posts = pd.DataFrame([
        {"ticker": "0700.HK", "source": "test", "url": "https://example.com/1",
         "text": "$385 is great support. Support 22. Support 5%."},
        {"ticker": "005380.KS", "source": "test", "url": "https://example.com/2",
         "text": "25만원 지지. 5 지지. 25% 지지."},
    ])
    quotes = pd.DataFrame([
        {"ticker": "0700.HK", "price": 386.6, "currency": "HKD"},
        {"ticker": "005380.KS", "price": 269500, "currency": "KRW"},
    ])
    levels = module.community_levels(posts, quotes)
    assert set(levels.level_numeric) == {385.0, 250000.0}
    assert set(levels.kind) == {"support"}
    assert levels.url.notna().all()


def test_pipeline_and_report_share_one_levels_implementation():
    # The report's _levels must give the same verdict as the pipeline's
    # community_levels on the same text: "Support 5%" is not a level of 5,
    # and "Support 22" is not a level of 22.
    support, resistance = _levels(
        ["$385 is great support. Support 22. Support 5%."],
        ticker="0700.HK", quote_price=386.6, currency="HKD")
    assert support == "385.00 HKD"
    assert resistance == "Not detected"


def test_report_levels_reject_bare_numbers_and_percentages():
    support, _ = _levels(["Support 22. Support 5%. Resistance $400."],
                         ticker="0700.HK", quote_price=386.6, currency="HKD")
    assert support == "Not detected"
    _, resistance = _levels(["Support 22. Support 5%. Resistance $400."],
                            ticker="0700.HK", quote_price=386.6, currency="HKD")
    assert "400" in resistance


def test_report_levels_require_price_within_range():
    # $900 is outside 0.5x-1.5x of a 386.6 quote, so it is not a level.
    support, _ = _levels(["Support $900."], ticker="0700.HK",
                         quote_price=386.6, currency="HKD")
    assert support == "Not detected"


def _report_frames(post_text, post_time_utc):
    posts = pd.DataFrame([{
        "ticker": "0700.HK", "source": "Moomoo", "timestamp_utc": post_time_utc,
        "text": post_text, "likes": 1, "reposts": None, "views": None,
        "author_followers": None, "post_id": "p1", "url": "https://example.com/1",
    }])
    prices = pd.DataFrame([{
        "ticker": "0700.HK", "date": "2026-10-01", "close": 386.6,
    }])
    assets = pd.DataFrame([{
        "market": "HKEX", "exchange": "HKEX", "ticker": "0700.HK",
        "asset_name": "Tencent Holdings", "currency": "HKD",
    }])
    return posts, prices, assets


def test_report_uses_market_cutoff_not_2359():
    # 16:30 Hong Kong time is after the HKEX 16:10 cutoff. With only the
    # 2026-10-01 session available, the post must not count for that session.
    posts, prices, assets = _report_frames("bullish breakout", "2026-10-01T08:30:00Z")
    rows = _report_rows(posts, prices, assets, "HKEX", "Asia/Hong_Kong")
    assert rows[0]["mentions"] == 0
    # The same post before the cutoff counts.
    posts, prices, assets = _report_frames("bullish breakout", "2026-10-01T07:30:00Z")
    rows = _report_rows(posts, prices, assets, "HKEX", "Asia/Hong_Kong")
    assert rows[0]["mentions"] == 1
    # An explicit 23:59 cutoff counts the late post (the old behaviour).
    posts, prices, assets = _report_frames("bullish breakout", "2026-10-01T08:30:00Z")
    rows = _report_rows(posts, prices, assets, "HKEX", "Asia/Hong_Kong", cutoff="23:59")
    assert rows[0]["mentions"] == 1
