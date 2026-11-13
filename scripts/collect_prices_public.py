#!/usr/bin/env python3
"""Collect real daily OHLCV bars from free public Yahoo Finance chart endpoints.

No API key, login, paid service, or synthetic/forward-filled data is used.
"""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "config" / "assets.csv"
RAW_DIR = ROOT / "data" / "raw" / "prices_public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
RAW_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

# The task date is explicit and is retained for auditability; retrieval uses actual UTC now.
TASK_DATE = "2026-11-13"
ENDPOINTS = ["https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
             "https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"]
EXCHANGE_TZ = {"HKEX": "Asia/Hong_Kong", "KRX": "Asia/Seoul"}
USER_AGENT = "Mozilla/5.0 (compatible; public-price-collector/1.0)"


def read_assets():
    with ASSETS.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_window():
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=730)
    return int(start.timestamp()), int(end.timestamp()), end


def fetch_one(asset, period1, period2):
    ticker = asset["ticker"]
    errors = []
    for endpoint in ENDPOINTS:
        url = endpoint.format(ticker=ticker)
        params = {"period1": period1, "period2": period2, "interval": "1d",
                  "events": "history", "includeAdjustedClose": "false"}
        try:
            response = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
            source_url = response.url
            raw_path = RAW_DIR / f"{ticker}.json"
            raw_path.write_text(response.text, encoding="utf-8")
            if response.status_code != 200:
                errors.append(f"{endpoint}: HTTP {response.status_code}")
                continue
            payload = response.json()
            result = payload.get("chart", {}).get("result")
            chart_error = payload.get("chart", {}).get("error")
            if chart_error or not result:
                errors.append(f"{endpoint}: chart error {chart_error or 'empty result'}")
                continue
            meta = result[0].get("meta", {})
            timestamps = result[0].get("timestamp", [])
            quote = (result[0].get("indicators", {}).get("quote") or [{}])[0]
            rows = []
            tzname = EXCHANGE_TZ[asset["exchange"]]
            tz = ZoneInfo(tzname)
            for i, ts in enumerate(timestamps):
                values = {k: (quote.get(k) or [None] * len(timestamps))[i]
                          for k in ("open", "high", "low", "close", "volume")}
                if any(v is None for v in values.values()):
                    continue
                local_dt = datetime.fromtimestamp(ts, timezone.utc).astimezone(tz)
                rows.append({"ticker": ticker, "date": local_dt.date().isoformat(), **values,
                             "currency": asset["currency"], "data_source": "Yahoo Finance chart API",
                             "source_url": source_url})
            # Persist a compact provenance record alongside the untouched response.
            return {"asset": asset, "rows": rows, "source_url": source_url,
                    "raw_file": str(raw_path.relative_to(ROOT)), "meta_timezone": meta.get("exchangeTimezoneName"),
                    "errors": errors, "endpoint": endpoint, "http_status": response.status_code,
                    "raw_sha256": hashlib.sha256(response.content).hexdigest()}
        except Exception as exc:
            errors.append(f"{endpoint}: {type(exc).__name__}: {exc}")
        time.sleep(1.0)
    return {"asset": asset, "rows": [], "source_url": None, "raw_file": None,
            "meta_timezone": None, "errors": errors, "endpoint": None,
            "http_status": None, "raw_sha256": None}


def main():
    assets = read_assets()
    period1, period2, retrieval_dt = get_window()
    # max_workers=3 satisfies the requested bounded concurrency.
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(fetch_one, asset, period1, period2) for asset in assets]
        results = [future.result() for future in futures]

    all_rows = []
    status_assets = []
    for result in results:
        df = pd.DataFrame(result["rows"])
        invalid = 0
        if not df.empty:
            numeric = ["open", "high", "low", "close", "volume"]
            for col in numeric:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            valid = (df["open"] > 0) & (df["high"] > 0) & (df["low"] > 0) & (df["close"] > 0) & (df["volume"] >= 0)
            invalid = int((~valid).sum())
            df = df.loc[valid].copy()
            before = len(df)
            df = df.sort_values("date").drop_duplicates(subset=["ticker", "date"], keep="last")
            duplicates_removed = before - len(df)
            all_rows.extend(df.to_dict("records"))
        else:
            duplicates_removed = 0
        dates = sorted({r["date"] for r in df.to_dict("records")}) if not df.empty else []
        latest_date = dates[-1] if dates else None
        task_date_delta_days = ((date.fromisoformat(TASK_DATE) - date.fromisoformat(latest_date)).days
                                if latest_date else None)
        status_assets.append({
            "ticker": result["asset"]["ticker"], "exchange": result["asset"]["exchange"],
            "currency": result["asset"]["currency"], "count": len(df),
            "date_start": dates[0] if dates else None, "date_end": dates[-1] if dates else None,
            "latest_close": float(df.iloc[-1]["close"]) if not df.empty else None,
            "latest_date": latest_date,
            "task_date_delta_days": task_date_delta_days,
            "source_timestamp_mismatch": bool(latest_date and latest_date != TASK_DATE),
            "invalid_rows_removed": invalid, "duplicates_removed": duplicates_removed,
            "endpoint": result["endpoint"], "source_url": result["source_url"],
            "raw_file": result["raw_file"], "raw_sha256": result["raw_sha256"],
            "reported_exchange_timezone": result["meta_timezone"], "errors": result["errors"]
        })

    columns = ["ticker", "date", "open", "high", "low", "close", "volume", "currency", "data_source", "source_url"]
    out = pd.DataFrame(all_rows, columns=columns)
    if not out.empty:
        out = out.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
        out.to_csv(NORMALIZED_DIR / "prices.csv", index=False, float_format="%.10g")
    else:
        pd.DataFrame(columns=columns).to_csv(NORMALIZED_DIR / "prices.csv", index=False)

    status = {
        "retrieval_utc": retrieval_dt.isoformat(), "task_date": TASK_DATE,
        "task_date_relation": "future relative to retrieval" if retrieval_dt.date().isoformat() < TASK_DATE else ("same day" if retrieval_dt.date().isoformat() == TASK_DATE else "past relative to retrieval"),
        "requested_window": {"period1_utc": datetime.fromtimestamp(period1, timezone.utc).isoformat(), "period2_utc": datetime.fromtimestamp(period2, timezone.utc).isoformat()},
        "endpoints": ENDPOINTS, "concurrency": 3, "assets_requested": len(assets),
        "assets_succeeded": sum(bool(a["count"]) for a in status_assets),
        "total_rows": len(out), "assets": status_assets,
        "failures": [a for a in status_assets if a["count"] == 0 or a["errors"]]
    }
    (NORMALIZED_DIR / "price_collection_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    (RAW_DIR / "provenance.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["assets_succeeded"] == len(assets) else 1


if __name__ == "__main__":
    sys.exit(main())
