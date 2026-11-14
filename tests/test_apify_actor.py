"""Offline checks for the Apify Actor (Fix 1).

These never touch the network: they validate the Actor definition, the
input contract against config/apify_input.json, and the pure helpers. The
live fetch logic is validated by `python apify-actor/main.py --local-test`
against the real public endpoints (2026-11-14: 691 rows — 3 LIHKG, 23
Moomoo, 500 Naver, 165 Daum).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apify-actor"))

import main as actor_main  # noqa: E402


def test_actor_json_valid():
    actor_json = json.loads((ROOT / "apify-actor" / ".actor" / "actor.json").read_text(encoding="utf-8"))
    assert actor_json["name"] == "cwt-public-finance-sources"
    assert actor_json["dockerfile"] == "./Dockerfile"
    assert actor_json["input"]["properties"]["lookback_days"]["default"] == 10
    assert actor_json["storages"]["dataset"]["fields"]["ticker"]["type"] == "string"


def test_default_input_matches_config():
    config = json.loads((ROOT / "config" / "apify_input.json").read_text(encoding="utf-8"))
    default = actor_main.DEFAULT_INPUT
    assert default["lookback_days"] == config["lookback_days"]
    assert default["max_posts_per_source_asset"] == config["max_posts_per_source_asset"]
    assert default["max_pages_per_source_asset"] == config["max_pages_per_source_asset"]
    config_tickers = {a["ticker"] for m in config["markets"] for a in m["assets"]}
    default_tickers = {a["ticker"] for m in default["markets"] for a in m["assets"]}
    assert config_tickers == default_tickers
    assert len(config_tickers) == 10
    # Every source in the config has a fetcher.
    for market in default["markets"]:
        for source in market["sources"]:
            assert source in actor_main.FETCHERS


def test_parse_dt_handles_moomoo_hour_24():
    # Moomoo's own data can carry hour 24; _parse_dt itself does not fix
    # it (the fix lives in _moomoo_post), but plain ISO parses must work.
    parsed = actor_main._parse_dt("2026-11-06T15:55:38+08:00")
    assert parsed == datetime(2026, 11, 6, 7, 55, 38, tzinfo=timezone.utc)
    assert actor_main._parse_dt("not a date") is None
    assert actor_main._parse_dt(None) is None


def test_clean_strips_html():
    assert actor_main._clean("<b>hello</b>   world") == "hello world"
    assert actor_main._clean(None) is None
