#!/usr/bin/env python3
"""Collect current Yahoo chart metadata snapshots for configured assets.

Uses range=1mo and interval=1d, but writes only quote metadata. It never writes
or updates normalized/prices.csv and never treats a provisional quote as an
official daily close.
"""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "config" / "assets.csv"
RAW_DIR = ROOT / "data" / "raw" / "quotes_public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
RAW_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)
CONCURRENCY = 3
ENDPOINT = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
EXCHANGE_TZ = {"HKEX": "Asia/Hong_Kong", "KRX": "Asia/Seoul"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; public-quote-collector/1.0)"}
COLUMNS = ["ticker", "quote_timestamp_utc", "quote_date_local", "price", "currency",
           "data_source", "source_url", "retrieved_at_utc", "daily_bar_close_missing"]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_one(asset: dict[str, str], retrieved: datetime) -> dict:
    ticker = asset["ticker"]
    url = ENDPOINT.format(ticker=ticker)
    params = {"range": "1mo", "interval": "1d"}
    raw_path = RAW_DIR / f"{ticker}.json"
    meta_path = RAW_DIR / f"{ticker}.meta.json"
    result = {"asset": asset, "source_url": None, "raw_file": str(raw_path.relative_to(ROOT)),
              "raw_sha256": None, "status_code": None, "row": None, "errors": []}
    try:
        response = requests.get(url, params=params, headers=HEADERS, timeout=30)
        raw_path.write_bytes(response.content)
        result.update(source_url=response.url, status_code=response.status_code,
                      raw_sha256=hashlib.sha256(response.content).hexdigest())
        meta_path.write_text(json.dumps({"requested_url": url, "final_url": response.url,
            "params": params, "status_code": response.status_code,
            "retrieved_at_utc": iso(retrieved), "sha256": result["raw_sha256"]}, indent=2), encoding="utf-8")
        if response.status_code != 200:
            result["errors"].append(f"HTTP {response.status_code}")
            return result
        payload = response.json()
        chart = payload.get("chart", {})
        if chart.get("error") or not chart.get("result"):
            result["errors"].append(f"chart error: {chart.get('error') or 'empty result'}")
            return result
        item = chart["result"][0]
        meta = item.get("meta") or {}
        quote_ts = meta.get("regularMarketTime")
        price = meta.get("regularMarketPrice")
        if quote_ts is None or price is None:
            result["errors"].append("missing regularMarketTime or regularMarketPrice")
            return result
        quote_dt = datetime.fromtimestamp(float(quote_ts), timezone.utc)
        tz = ZoneInfo(EXCHANGE_TZ[asset["exchange"]])
        timestamps = item.get("timestamp") or []
        quote = ((item.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quote.get("close") or []
        latest_close = closes[-1] if closes else None
        daily_bar_close_missing = latest_close is None
        result["row"] = {"ticker": ticker, "quote_timestamp_utc": iso(quote_dt),
            "quote_date_local": quote_dt.astimezone(tz).date().isoformat(), "price": price,
            "currency": meta.get("currency") or asset["currency"],
            "data_source": "Yahoo Finance chart API metadata (provisional quote; not official daily close)",
            "source_url": result["source_url"], "retrieved_at_utc": iso(retrieved),
            "daily_bar_close_missing": daily_bar_close_missing}
        result["latest_bar_timestamp"] = timestamps[-1] if timestamps else None
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        meta_path.write_text(json.dumps({"requested_url": url, "retrieved_at_utc": iso(retrieved), "error": repr(exc)}, indent=2), encoding="utf-8")
    return result


def main() -> int:
    started = datetime.now(timezone.utc)
    with ASSETS.open(newline="", encoding="utf-8") as f:
        assets = list(csv.DictReader(f))
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda a: fetch_one(a, started), assets))
    rows = [r["row"] for r in results if r["row"] is not None]
    rows.sort(key=lambda r: r["ticker"])
    with (NORMALIZED_DIR / "quotes.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c) for c in COLUMNS} for row in rows)
    status_assets = []
    for result in results:
        row = result["row"]
        status_assets.append({"ticker": result["asset"]["ticker"], "asset_name": result["asset"]["asset_name"],
            "status_code": result["status_code"], "quote_timestamp_utc": row.get("quote_timestamp_utc") if row else None,
            "quote_date_local": row.get("quote_date_local") if row else None,
            "price": row.get("price") if row else None, "currency": row.get("currency") if row else None,
            "daily_bar_close_missing": row.get("daily_bar_close_missing") if row else None,
            "source_url": result["source_url"], "raw_file": result["raw_file"],
            "raw_sha256": result["raw_sha256"], "errors": result["errors"]})
    status = {"collection_started_at_utc": iso(started), "collection_finished_at_utc": iso(datetime.now(timezone.utc)),
        "method": "Yahoo Finance chart endpoint GET range=1mo interval=1d; metadata snapshot only",
        "endpoint": ENDPOINT, "concurrency": CONCURRENCY, "assets_requested": len(assets),
        "assets_succeeded": len(rows), "total_records": len(rows),
        "explicit_no_exa_compliance": "Exa and Apify were not called; no keys, login, or paid service used.",
        "historical_prices_untouched": True, "provisional_quote_note": "These post-close metadata quotes may later be labelled provisional outcome checks; they are not official daily closes.",
        "assets": status_assets, "failures": [x for x in status_assets if x["status_code"] != 200 or x["errors"]]}
    (NORMALIZED_DIR / "quote_collection_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW_DIR / "provenance.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if not status["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
