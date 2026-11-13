#!/usr/bin/env python3
"""Collect headline-only Google News RSS items for configured assets.

This collector deliberately uses only the public Google News RSS route: no Exa,
Apify, API keys, login, paid service, synthetic timestamps, or synthetic rows.
"""
from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import requests

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "config" / "assets.csv"
RAW_DIR = ROOT / "data" / "raw" / "news_public"
NORMALIZED_DIR = ROOT / "data" / "normalized"
RAW_DIR.mkdir(parents=True, exist_ok=True)
NORMALIZED_DIR.mkdir(parents=True, exist_ok=True)

DAYS = 10
MAX_ITEMS = 15
CONCURRENCY = 3
PROVIDER = "Google News RSS (Exa substitute)"
BASE_URL = "https://news.google.com/rss/search?q={}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; public-news-collector/1.0)",
           "Accept": "application/rss+xml, application/xml, text/xml"}
COLUMNS = ["title", "text", "published_at_utc", "url", "source", "news_provider",
           "retrieved_at_utc", "asset_name", "ticker"]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_pubdate(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value.strip())
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def child_text(item: ET.Element, name: str) -> str | None:
    node = item.find(name)
    return node.text.strip() if node is not None and node.text else None


def fetch_one(asset: dict[str, str], cutoff: datetime, retrieved: datetime) -> dict:
    ticker = asset["ticker"]
    query = f'"{asset["asset_name"]}" OR "{ticker}"'
    url = BASE_URL.format(quote_plus(query))
    raw_path = RAW_DIR / f"{ticker}.xml"
    meta_path = RAW_DIR / f"{ticker}.meta.json"
    result = {"asset": asset, "requested_url": url, "final_url": None,
              "raw_file": str(raw_path.relative_to(ROOT)), "raw_sha256": None,
              "status_code": None, "rows": [], "errors": [], "items_seen": 0,
              "unusable_dates": 0}
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        raw_path.write_bytes(response.content)
        result.update(final_url=response.url, status_code=response.status_code,
                      raw_sha256=hashlib.sha256(response.content).hexdigest())
        meta_path.write_text(json.dumps({"requested_url": url, "final_url": response.url,
            "status_code": response.status_code, "content_type": response.headers.get("content-type"),
            "retrieved_at_utc": iso(retrieved), "sha256": result["raw_sha256"]},
            indent=2), encoding="utf-8")
        if response.status_code != 200:
            result["errors"].append(f"HTTP {response.status_code}")
            return result
        root = ET.fromstring(response.content)
        items = root.findall("./channel/item")
        result["items_seen"] = len(items)
        parsed = []
        for item in items:
            published = parse_pubdate(child_text(item, "pubDate"))
            if published is None:
                result["unusable_dates"] += 1
                continue
            if not (cutoff <= published <= retrieved):
                continue
            title = child_text(item, "title")
            link = child_text(item, "link")
            source = child_text(item, "source")
            if not title or not link:
                continue
            parsed.append({"title": title, "text": title, "published_at_utc": iso(published),
                "url": link, "source": source, "news_provider": PROVIDER,
                "retrieved_at_utc": iso(retrieved), "asset_name": asset["asset_name"],
                "ticker": ticker})
        parsed.sort(key=lambda x: x["published_at_utc"], reverse=True)
        result["rows"] = parsed[:MAX_ITEMS]
    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
        meta_path.write_text(json.dumps({"requested_url": url, "retrieved_at_utc": iso(retrieved),
            "error": repr(exc)}, indent=2), encoding="utf-8")
    return result


def main() -> int:
    started = datetime.now(timezone.utc)
    cutoff = started - timedelta(days=DAYS)
    with ASSETS.open(newline="", encoding="utf-8") as f:
        assets = list(csv.DictReader(f))
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda a: fetch_one(a, cutoff, started), assets))
    rows = []
    status_assets = []
    for result in results:
        rows.extend(result["rows"])
        dates = [r["published_at_utc"] for r in result["rows"]]
        status_assets.append({"ticker": result["asset"]["ticker"], "asset_name": result["asset"]["asset_name"],
            "query_url": result["requested_url"], "final_url": result["final_url"],
            "status_code": result["status_code"], "items_seen": result["items_seen"],
            "records_retained": len(result["rows"]), "date_start_utc": min(dates) if dates else None,
            "date_end_utc": max(dates) if dates else None, "unusable_dates": result["unusable_dates"],
            "raw_file": result["raw_file"], "raw_sha256": result["raw_sha256"], "errors": result["errors"]})
    rows.sort(key=lambda r: (r["ticker"], r["published_at_utc"], r["url"]))
    with (NORMALIZED_DIR / "news_public.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows({c: row.get(c) for c in COLUMNS} for row in rows)
    status = {"collection_started_at_utc": iso(started),
        "collection_finished_at_utc": iso(datetime.now(timezone.utc)), "cutoff_utc": iso(cutoff),
        "window_days": DAYS, "max_items_per_ticker": MAX_ITEMS, "concurrency": CONCURRENCY,
        "method": "Public Google News RSS over HTTP; headline-only; no Exa, Apify, keys, login, or paid service",
        "explicit_no_exa_compliance": "Exa was not called because free credits are USD0 and auto recharge is off.",
        "news_provider": PROVIDER, "assets_requested": len(assets), "assets_succeeded": sum(bool(x["rows"]) for x in results),
        "total_records": len(rows), "assets": status_assets,
        "failures": [x for x in status_assets if x["status_code"] != 200 or x["errors"]]}
    (NORMALIZED_DIR / "news_collection_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    (RAW_DIR / "provenance.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if not status["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
