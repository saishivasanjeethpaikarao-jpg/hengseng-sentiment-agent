"""Hand-labelled sentiment accuracy check (Fix 5).

100 real collected posts, labelled by hand (bullish / bearish / neutral
toward the ticker): 40 Naver, 25 Daum, 20 Moomoo, 3 LIHKG, 12 RSS headlines.
Fixture: tests/fixtures/labelled_sentiment_sample.csv.

MEASURED ACCURACY (2026-11-14, keyword baseline, direction threshold 0.1):
    overall  24 / 100  (24%)
    English  17 / 32   (53%)
    Korean    6 / 65   ( 9%)
    Chinese   1 / 3    (33%, n=3 — meaningless)

That is the honest result: the keyword lexicon is barely above the 33%
chance level overall, and systematically wrong on Korean forum text
(sarcasm, conditionals, news quotes, slang — "올라야 본전", "자사주 매입으로
버티는 주가", PPI "상승" as bad news). The thresholds below are a REGRESSION
FLOOR (fail loudly if a future change makes the scorer worse), not a quality
claim. The sentiment feature in the pipeline stays labelled "exploratory
only; too few sessions for a reliable edge claim" for exactly this reason —
do not promote it to a validated signal on the strength of this check.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from src.cwt_sentiment.sentiment import direction_from_score, score_sentiment

FIXTURE = Path(__file__).parent / "fixtures" / "labelled_sentiment_sample.csv"


def _load_rows():
    with FIXTURE.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _predicted(text: str) -> str:
    return direction_from_score(score_sentiment(text)).lower()


def test_labelled_sample_accuracy():
    rows = _load_rows()
    assert len(rows) == 100
    assert {r["label"] for r in rows} == {"positive", "negative", "neutral"}

    by_lang: dict[str, list[bool]] = {}
    overall: list[bool] = []
    for row in rows:
        correct = _predicted(row["text"]) == row["label"]
        overall.append(correct)
        by_lang.setdefault(row["language"], []).append(correct)

    overall_acc = sum(overall) / len(overall)
    # Regression floor only — see module docstring. These numbers are weak
    # and the sentiment feature must stay exploratory.
    assert overall_acc >= 0.20, f"overall labelled accuracy {overall_acc:.2f} < 0.20"
    en_acc = sum(by_lang["en"]) / len(by_lang["en"])
    assert en_acc >= 0.45, f"English labelled accuracy {en_acc:.2f} < 0.45"
    ko_acc = sum(by_lang["ko"]) / len(by_lang["ko"])
    assert ko_acc >= 0.05, f"Korean labelled accuracy {ko_acc:.2f} < 0.05"
    # Chinese n=3 is too small to assert anything.


def test_labelled_sample_has_all_sources():
    rows = _load_rows()
    sources = {r["source"] for r in rows}
    assert {"naver_finance", "daum_finance", "Moomoo", "LIHKG", "news_rss"} <= sources
