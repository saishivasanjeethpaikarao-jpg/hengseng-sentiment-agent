"""Optional public-report tests; no network requests or credentials are used."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

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
