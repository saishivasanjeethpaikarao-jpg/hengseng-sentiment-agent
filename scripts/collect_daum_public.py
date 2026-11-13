#!/usr/bin/env python3
"""Collect Daum Finance talks through the observed public JSON endpoint.

Requests-only, unauthenticated, sequential and rate-limited. Daum's observed
createdAt values are naive strings; this collector explicitly interprets them
as Asia/Seoul site-local time, then stores UTC timestamps.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html as html_lib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ASSETS = {
    "005930.KS": ("005930", "Samsung Electronics"),
    "000660.KS": ("000660", "SK hynix"),
    "035420.KS": ("035420", "Naver Corporation"),
    "035720.KS": ("035720", "Kakao Corporation"),
    "005380.KS": ("005380", "Hyundai Motor"),
}
COLUMNS = ["ticker", "source", "timestamp_utc", "text", "likes", "reposts", "views", "author_followers", "post_id", "url"]
SOURCE = "daum_finance"
ENDPOINT = "https://m.finance.daum.net/api/home/daum"
PAGE_URL = "https://m.finance.daum.net/quotes/A{code}/talks"
REFERER = "https://m.finance.daum.net/quotes/A{code}/talks"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; internship-public-collector/1.0)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
}
SEOUL = ZoneInfo("Asia/Seoul")
UTC = timezone.utc


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_created_at(value: object) -> tuple[datetime | None, str]:
    if value in (None, ""):
        return None, "missing"
    text = str(value).strip()
    try:
        # Explicit offset/suffix is honored exactly; naive Daum values are
        # documented site-local timestamps, not silently assumed to be UTC.
        normalized = text.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=SEOUL).astimezone(UTC), "naive_assumed_Asia/Seoul"
        return parsed.astimezone(UTC), "explicit_timezone"
    except (TypeError, ValueError):
        return None, "unparseable"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    # BeautifulSoup removes tags; html.unescape handles entities in plain JSON.
    text = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()


def request_page(session: requests.Session, root: Path, code: str, page: int) -> tuple[dict | None, dict]:
    params = {"path": f"/content/debates/A{code}?page={page}&perPage=30&notice=true"}
    requested_url = requests.Request("GET", ENDPOINT, params=params).prepare().url
    label = f"daum_{code}_page{page}"
    raw_path = root / "data/raw/daum_public" / f"{label}.json"
    meta_path = root / "data/raw/daum_public" / f"{label}.meta.json"
    started = datetime.now(UTC)
    meta = {"requested_url": requested_url, "endpoint": ENDPOINT, "params": params,
            "retrieved_at_utc": iso(started), "raw_path": str(raw_path.relative_to(root))}
    try:
        response = session.get(ENDPOINT, params=params, headers={"Referer": REFERER.format(code=code)}, timeout=30)
        raw_path.write_bytes(response.content)
        meta.update({"final_url": response.url, "status_code": response.status_code,
                     "content_type": response.headers.get("content-type"),
                     "sha256": hashlib.sha256(response.content).hexdigest()})
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        response.raise_for_status()
        payload = response.json()
        return payload, meta
    except Exception as exc:
        meta["error"] = repr(exc)
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return None, meta


def normalize_posts(payload: dict, ticker: str, code: str, page: int, cutoff: datetime, now: datetime) -> tuple[list[dict], dict]:
    posts = (((payload or {}).get("data") or {}).get("posts") or [])
    rows: list[dict] = []
    timestamp_notes: dict[str, int] = {}
    for post in posts:
        dt, note = parse_created_at(post.get("createdAt"))
        timestamp_notes[note] = timestamp_notes.get(note, 0) + 1
        if dt is None or not (cutoff <= dt <= now):
            continue
        post_id = post.get("id")
        if post_id in (None, ""):
            continue
        # The observed API URL is retained verbatim as the source URL for the row.
        params = {"path": f"/content/debates/A{code}?page={page}&perPage=30&notice=true"}
        source_url = requests.Request("GET", ENDPOINT, params=params).prepare().url
        text = " ".join(x for x in (clean_text(post.get("title")), clean_text(post.get("content"))) if x)
        rows.append({
            "ticker": ticker, "source": SOURCE, "timestamp_utc": iso(dt), "text": text,
            "likes": post.get("agreeCount"), "reposts": None, "views": post.get("readCount"),
            "author_followers": None, "post_id": str(post_id), "url": source_url,
        })
    return rows, {"records_seen": len(posts), "records_in_window": len(rows), "timestamp_parse_notes": timestamp_notes}


def dedupe(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    out: list[dict] = []
    for row in rows:
        key = (row.get("source"), row.get("ticker"), row.get("post_id"))
        if key in seen:
            continue
        seen.add(key)
        out.append({column: row.get(column) for column in COLUMNS})
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=".")
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--delay-seconds", type=float, default=0.55)
    args = parser.parse_args()
    root = Path(args.out).resolve()
    raw_dir = root / "data/raw/daum_public"
    norm_dir = root / "data/normalized"
    raw_dir.mkdir(parents=True, exist_ok=True)
    norm_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    cutoff = started - timedelta(days=args.days)
    session = requests.Session()
    session.headers.update(HEADERS)
    daum_rows: list[dict] = []
    status_sources: dict[str, dict] = {}
    failures: list[str] = []

    for ticker, (code, name) in ASSETS.items():
        ticker_rows: list[dict] = []
        for page in range(1, args.max_pages + 1):
            if page > 1:
                time.sleep(max(0.5, args.delay_seconds))
            payload, meta = request_page(session, root, code, page)
            key = f"{SOURCE}:{ticker}:page{page}"
            rec = {"ticker": ticker, "asset_name": name, "source": SOURCE, "page": page,
                   "requested_url": meta.get("requested_url"), "raw_path": meta.get("raw_path"),
                   "status_code": meta.get("status_code"), "records_seen": 0, "records_in_window": 0,
                   "usable_timestamp_count": 0, "min_timestamp_utc": None, "max_timestamp_utc": None,
                   "access_failure": meta.get("error"), "timestamp_assumption": "naive createdAt interpreted as Asia/Seoul; explicit offsets honored",
                   "parser_note": "Daum API data.posts; page size 30; stop at 10-day UTC boundary or max 5 pages"}
            if payload is None:
                status_sources[key] = rec
                failures.append(key)
                break
            rows, info = normalize_posts(payload, ticker, code, page, cutoff, started)
            rec.update(info, usable_timestamp_count=sum(bool(r.get("timestamp_utc")) for r in rows))
            if rows:
                dates = [r["timestamp_utc"] for r in rows]
                rec.update(min_timestamp_utc=min(dates), max_timestamp_utc=max(dates))
            status_sources[key] = rec
            ticker_rows.extend(rows)
            daum_rows.extend(rows)
            # Pages are newest-first in the observed response. Once the oldest
            # retained/seen timestamp is before cutoff, later pages cannot help.
            seen_dates = [parse_created_at(p.get("createdAt"))[0] for p in (((payload.get("data") or {}).get("posts")) or [])]
            valid_seen = [d for d in seen_dates if d is not None]
            if valid_seen and min(valid_seen) < cutoff:
                break
        
    daum_rows = dedupe(daum_rows)
    csv_path = norm_dir / "kr_posts.csv"
    existing: list[dict] = []
    if csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            existing = list(csv.DictReader(handle))
    combined = dedupe(existing + daum_rows)
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(combined)

    finished = datetime.now(UTC)
    source_counts = {f"{SOURCE}:{ticker}": sum(1 for row in daum_rows if row["ticker"] == ticker) for ticker in ASSETS}
    status = {
        "collection_started_at_utc": iso(started), "collection_finished_at_utc": iso(finished),
        "cutoff_utc": iso(cutoff), "window_days": args.days, "max_pages_per_ticker": args.max_pages,
        "method": "requests HTTP only; no keys, login, browser, proxy, paid API, Apify, or Exa",
        "endpoint": ENDPOINT, "referer_template": REFERER,
        "rate_limit_seconds_between_pages": max(0.5, args.delay_seconds),
        "timestamp_policy": "Daum createdAt is observed as naive site-local time; interpreted explicitly as Asia/Seoul and converted to UTC. Values with an explicit offset use that offset.",
        "sources": status_sources, "failures": failures, "total_daum_records": len(daum_rows),
        "total_normalized_records_after_append": len(combined), "count_by_ticker": source_counts,
        "normalized_csv": str(csv_path.relative_to(root)), "raw_directory": str(raw_dir.relative_to(root)),
    }
    (norm_dir / "daum_collection_status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "retrieved_at_utc": iso(finished), "scope": {"tickers": list(ASSETS), "source": "Daum Finance talks", "window": f"{iso(cutoff)} through {iso(started)}"},
        "method": status["method"], "observed_endpoint": ENDPOINT, "observed_page_url": PAGE_URL.format(code="005930"),
        "pagination": {"parameter": "path=/content/debates/A{code}?page={page}&perPage=30&notice=true", "max_pages_per_ticker": args.max_pages, "stop_rule": "10-day UTC boundary or max pages", "per_page": 30},
        "fields": {"likes": "agreeCount", "views": "readCount", "followers": None, "post_id": "id", "text": "title + content sanitized from HTML/entities"},
        "timestamp_assumption": status["timestamp_policy"], "raw_directory": str(raw_dir.relative_to(root)), "normalized_csv": str(csv_path.relative_to(root)),
        "records_by_ticker": source_counts, "access_failures": failures,
    }
    (norm_dir / "daum_collection_provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    # Resolve the old Daum block while preserving all Naver rows and history.
    kr_status_path = norm_dir / "kr_collection_status.json"
    if kr_status_path.exists():
        kr_status = json.loads(kr_status_path.read_text(encoding="utf-8"))
        for ticker, (code, name) in ASSETS.items():
            key = f"{SOURCE}:{ticker}"
            pages = [v for k, v in status_sources.items() if k.startswith(key + ":page")]
            kr_status.setdefault("sources", {})[key] = {"ticker": ticker, "asset_name": name, "source": SOURCE, "requested_url": PAGE_URL.format(code=code), "pages_requested": len(pages), "records_seen": sum(p.get("records_seen", 0) for p in pages), "records_in_window": source_counts[key], "usable_timestamp_count": source_counts[key], "min_timestamp_utc": min((p["min_timestamp_utc"] for p in pages if p.get("min_timestamp_utc")), default=None), "max_timestamp_utc": max((p["max_timestamp_utc"] for p in pages if p.get("max_timestamp_utc")), default=None), "raw_paths": [p["raw_path"] for p in pages], "access_failure": None if not any(p.get("access_failure") for p in pages) else [p.get("access_failure") for p in pages if p.get("access_failure")], "parser_note": "Observed public Daum JSON endpoint; naive createdAt explicitly interpreted as Asia/Seoul."}
        kr_status["total_records"] = len(combined)
        kr_status["count_by_ticker_source"] = {f"{source}:{ticker}": sum(1 for row in combined if row.get("source") == source and row.get("ticker") == ticker) for source in ("naver_finance", SOURCE) for ticker in ASSETS}
        kr_status["collection_finished_at_utc"] = iso(finished)
        kr_status["method"] = "requests HTTP only; Naver and observed Daum public JSON endpoints; no browser, login, proxy, Apify, Exa, paid API, or secret"
        kr_status_path.write_text(json.dumps(kr_status, ensure_ascii=False, indent=2), encoding="utf-8")
    kr_prov_path = norm_dir / "kr_collection_provenance.json"
    if kr_prov_path.exists():
        kr_prov = json.loads(kr_prov_path.read_text(encoding="utf-8"))
        kr_prov["retrieved_at_utc"] = iso(finished)
        kr_prov["observed_routes"]["daum_api"] = ENDPOINT
        kr_prov["pagination"]["daum"] = "path=/content/debates/A{code}?page={page}&perPage=30&notice=true; max 5 pages/ticker; 0.55s delay"
        kr_prov["raw_evidence"] = "data/raw/kr_public/ and data/raw/daum_public/"
        kr_prov["blockers"] = [b for b in kr_prov.get("blockers", []) if "Daum" not in b and "daum" not in b]
        kr_prov.setdefault("resolved_notes", []).append("Daum Finance talks collected from the observed public API endpoint; see daum_collection_status.json and daum_collection_provenance.json.")
        kr_prov_path.write_text(json.dumps(kr_prov, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"daum_records": len(daum_rows), "normalized_records": len(combined), "counts": source_counts, "status": str(norm_dir / "daum_collection_status.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
