"""Strict support/resistance extraction from community post text.

Single implementation shared by the offline pipeline
(``scripts/run_real_pipeline.py``) and the visual report
(``cwt_sentiment.report``). A candidate level is only accepted when it
looks like money: it must carry a currency marker (``$``/``₩``/``만``/``천``/
``원``/HKD/KRW or a thousands comma) and fall within 0.5x-1.5x of the
ticker's reference price. Bare numbers such as "Support 22" or
"Support 5%" are rejected -- they are counts and percentages, not prices.
"""

from __future__ import annotations

import re

import pandas as pd


def community_levels(posts: pd.DataFrame, quotes: pd.DataFrame) -> pd.DataFrame:
    """Extract money-like support/resistance levels with evidence.

    ``posts`` needs ``ticker``, ``text`` (``url``/``source`` optional).
    ``quotes`` needs ``ticker``, ``price`` (``currency`` optional).
    Returns one row per (ticker, kind, level, url) with the evidence snippet.
    """
    rows = []
    quote_map = quotes.set_index("ticker").price.to_dict()
    currencies = quotes.set_index("ticker").currency.to_dict() if "currency" in quotes else {}
    amount = r"[$₩]?\s*\d[\d,]*(?:\.\d+)?\s*(?:만(?:\s*원)?|천(?:\s*원)?|원|HKD|KRW)?"
    for row in posts.to_dict("records"):
        text = str(row.get("text", ""))
        for kind, words in [("support", r"support|支撐|支撑|지지"),
                            ("resistance", r"resistance|阻力|저항")]:
            # The gap before the amount must not swallow the currency marker:
            # "[^\d\n]{0,22}" would eat the "$" in "Resistance $400", leaving
            # a bare "400" that the money check then (correctly) rejects.
            patterns = [rf"(?:{words})[^\d\n$₩]{{0,22}}({amount})",
                        rf"({amount})[^\d\n$₩]{{0,25}}(?:{words})"]
            for pattern in patterns:
                for found in re.finditer(pattern, text, re.IGNORECASE):
                    raw = found.group(1).strip()
                    if not re.search(r"[$₩]|만|천|원|HKD|KRW|,\d{3}", raw, re.IGNORECASE):
                        continue
                    suffix = text[found.end(1):found.end(1) + 5].lstrip()
                    if suffix.startswith(("%", "％", "명", "개", "年", "년", "月", "월")):
                        continue
                    number = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
                    if not number:
                        continue
                    value = float(number.group().replace(",", "")) * (
                        10000 if "만" in raw else 1000 if "천" in raw else 1)
                    reference = quote_map.get(row["ticker"])
                    if not reference or not 0.5 * reference <= value <= 1.5 * reference:
                        continue
                    label = f"{value:,.2f} {currencies.get(row['ticker'], '')}".strip()
                    rows.append(dict(ticker=row["ticker"], kind=kind, level=label,
                                     raw_level=raw, level_numeric=value,
                                     evidence=text[max(0, found.start() - 45):min(len(text), found.end() + 60)],
                                     url=row.get("url", ""), source=row.get("source", "")))
    return pd.DataFrame(
        rows, columns=["ticker", "kind", "level", "raw_level", "level_numeric",
                       "evidence", "url", "source"]
    ).drop_duplicates(["ticker", "kind", "level", "url"])
