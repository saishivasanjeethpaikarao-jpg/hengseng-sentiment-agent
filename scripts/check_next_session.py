#!/usr/bin/env python3
"""Genuinely prospective n+1 check (Fix 7).

Compares the FROZEN next-session forecasts
(docs/frozen-run-2026-11-14/reports/next_session_forecasts.csv, written
2026-11-14 from the 2026-11-13 close) against the OFFICIAL daily close of
the next session, Monday 2026-11-16 — verified a regular full trading day
on both exchanges (see docs/prospective-check-2026-11-16.md).

Run only AFTER the session closes (both markets shut 16:10 HKT / 15:40 KST
on 2026-11-16; Yahoo daily bars are usually published a few hours later):

    python scripts/check_next_session.py

It fetches the 2026-11-16 daily bar for each ticker from the Yahoo Finance
chart API (the same endpoint collect_prices_public.py uses — official daily
closes, not provisional quotes), writes
reports/prospective-check-2026-11-16.csv, and prints the outcome.

Exit codes: 0 = all 10 tickers checked; 2 = a 2026-11-16 bar is not
published yet (retry later — do NOT substitute a provisional quote).
"""

from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
FORECASTS = ROOT / "docs" / "frozen-run-2026-11-14" / "reports" / "next_session_forecasts.csv"
OUT = ROOT / "reports" / "prospective-check-2026-11-16.csv"
SESSION_DATE = "2026-11-16"
ENDPOINTS = [
    "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
    "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}",
]
USER_AGENT = "Mozilla/5.0 (compatible; public-price-collector/1.0)"


def fetch_close(ticker: str) -> float | None:
    """Official daily close for SESSION_DATE, or None if not published yet."""
    period1 = int(datetime(2026, 11, 15, tzinfo=timezone.utc).timestamp())
    period2 = int(datetime(2026, 11, 18, tzinfo=timezone.utc).timestamp())
    for endpoint in ENDPOINTS:
        try:
            resp = requests.get(
                endpoint.format(ticker=ticker),
                params={"period1": period1, "period2": period2, "interval": "1d",
                        "events": "history", "includeAdjustedClose": "false"},
                headers={"User-Agent": USER_AGENT}, timeout=30,
            )
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        try:
            result = resp.json()["chart"]["result"][0]
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        timestamps = result.get("timestamp") or []
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        for ts, close in zip(timestamps, closes):
            day = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
            if day == SESSION_DATE and close is not None:
                return float(close)
        return None  # endpoint answered but no bar for the session date
    return None


def main() -> int:
    now_hkt = datetime.now(ZoneInfo("Asia/Hong_Kong"))
    if now_hkt.date().isoformat() < SESSION_DATE:
        print(f"Too early: it is {now_hkt.date()} in Hong Kong; the session is {SESSION_DATE}.")
        return 2

    with FORECASTS.open(newline="", encoding="utf-8") as fh:
        forecasts = list(csv.DictReader(fh))

    rows = []
    missing = []
    for fc in forecasts:
        ticker = fc["ticker"]
        actual = fetch_close(ticker)
        if actual is None:
            missing.append(ticker)
            continue
        prev_close = float(fc["close"])
        predicted_close = float(fc["predicted_close"])
        predicted_return = float(fc["predicted_return"])
        realized_return = math.log(actual / prev_close)
        rows.append({
            "ticker": ticker,
            "market": fc["market"],
            "model": fc["model"],
            "prev_close_2026-11-13": prev_close,
            "predicted_close": predicted_close,
            "predicted_return": predicted_return,
            "actual_close_2026-11-16": actual,
            "realized_return": round(realized_return, 6),
            "abs_error": round(abs(predicted_return - realized_return), 6),
            "direction_correct": (predicted_return > 0) == (realized_return > 0),
            "session_date": SESSION_DATE,
            "source": "Yahoo Finance chart API daily bar",
            "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        })

    if missing:
        print(f"Not published yet for: {', '.join(sorted(set(missing)))}.")
        print("The 2026-11-16 daily bar is not on Yahoo yet — retry later. "
              "Do NOT substitute a provisional quote.")
        return 2

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for model in sorted({r["model"] for r in rows}):
        subset = [r for r in rows if r["model"] == model]
        mae = sum(r["abs_error"] for r in subset) / len(subset)
        direction = sum(r["direction_correct"] for r in subset) / len(subset)
        print(f"{model}: n={len(subset)}  MAE {mae * 100:.3f}%  direction {direction * 100:.0f}%")
    print(f"Wrote {OUT}")
    print("One session, 10 tickers: this can confirm or refute nothing about "
          "an edge. It only proves the forecast was frozen before the outcome.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
