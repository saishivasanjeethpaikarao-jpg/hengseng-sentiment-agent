"""Transparent baseline sentiment utilities; replace/validate for production use."""

from __future__ import annotations

import re

POSITIVE = {
    "bullish", "buy", "strong", "surge", "rally", "gain", "breakout", "undervalued",
    "看多", "看好", "利好", "上涨", "上漲", "升", "買入", "买入", "強勢", "强势",
    "매수", "호재", "상승", "강세", "돌파",
}
NEGATIVE = {
    "bearish", "sell", "weak", "drop", "fall", "crash", "loss", "overvalued",
    "看空", "利淡", "下跌", "跌", "沽出", "賣出", "卖出", "弱勢", "弱势",
    "매도", "악재", "하락", "약세", "급락",
}


def score_sentiment(text: object) -> float:
    """Return a simple bounded keyword score in [-1, 1]. Neutral/no-hit text scores 0.

    This is a starter baseline, not a finance-trained or validated multilingual model.
    """
    if text is None:
        return 0.0
    value = str(text).lower()
    # Use substring matching for CJK/Korean token forms; word boundaries for Latin terms.
    positive_hits = sum(value.count(term) for term in POSITIVE if not term.isascii())
    negative_hits = sum(value.count(term) for term in NEGATIVE if not term.isascii())
    latin_tokens = set(re.findall(r"[a-z]+", value))
    positive_hits += len(latin_tokens.intersection(term for term in POSITIVE if term.isascii()))
    negative_hits += len(latin_tokens.intersection(term for term in NEGATIVE if term.isascii()))
    total = positive_hits + negative_hits
    return 0.0 if total == 0 else float((positive_hits - negative_hits) / total)


def direction_from_score(score: float, threshold: float = 0.1) -> str:
    if score >= threshold:
        return "Bullish"
    if score <= -threshold:
        return "Bearish"
    return "Neutral"
