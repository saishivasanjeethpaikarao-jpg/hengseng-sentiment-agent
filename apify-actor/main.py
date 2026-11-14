#!/usr/bin/env python3
"""Custom Apify Actor: cwt-public-finance-sources (Fix 1).

Collects the 4 assignment sources x 10 tickers from public pages only —
LIHKG + Moomoo (HKEX), Naver + Daum (KRX) — over a 10-day lookback, and
pushes one row per retained post to the Actor dataset.

The fetch logic is the same public-endpoint approach the repo's local
collectors (scripts/collect_hk_public.py, collect_kr_feeds.py,
collect_daum_public.py) already proved works; the Actor only moves that
collection onto Apify so the run has an Actor ID, run ID and run log to
submit to Gilad. No paid proxy, no login, no Store Actor.

Run on Apify:
    apify push          # from this directory, signed in as Shiv's account
    # then start a run in the Apify Console with the input in actor.json,
    # or: apify call cwt-public-finance-sources --input-file input.json

Local test (no Apify account, no SDK needed — fetches the real public
endpoints and prints counts; --max-posts caps the output):
    python main.py --local-test --max-posts 5
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup, MarkupResemblesLocatorWarning

# _clean() feeds arbitrary post text (sometimes a bare URL) to BeautifulSoup;
# the locator warning is spurious here.
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

# --- endpoints (public, proven by the repo's local collectors) ---
LIHKG_API = "https://lihkg.com/api_v2/thread/search"
LIHKG_CATEGORY = "https://lihkg.com/api_v2/thread/category"
LIHKG_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Referer": "https://lihkg.com/",
    "X-Requested-With": "XMLHttpRequest",
}
MOOMOO_PAGE = "https://www.moomoo.com/stock/{code}-HK/community"
NAVER_API = "https://m.stock.naver.com/front-api/discussion/list"
DAUM_API = "https://m.finance.daum.net/api/home/daum"

DEFAULT_INPUT = {
    "lookback_days": 10,
    "max_posts_per_source_asset": 100,
    "max_pages_per_source_asset": 3,
    "minimum_request_delay_seconds": 2,
    "markets": [
        {
            "market": "HKEX",
            "sources": ["LIHKG", "Moomoo_Community"],
            "assets": [
                {"ticker": "0700.HK", "source_code": "00700", "name": "Tencent Holdings"},
                {"ticker": "9988.HK", "source_code": "09988", "name": "Alibaba Group"},
                {"ticker": "0005.HK", "source_code": "00005", "name": "HSBC Holdings"},
                {"ticker": "3690.HK", "source_code": "03690", "name": "Meituan"},
                {"ticker": "1299.HK", "source_code": "01299", "name": "AIA Group"},
            ],
        },
        {
            "market": "KRX",
            "sources": ["Naver_Finance_Stock_Discussion", "Daum_Finance_Forum"],
            "assets": [
                {"ticker": "005930.KS", "source_code": "005930", "name": "Samsung Electronics"},
                {"ticker": "000660.KS", "source_code": "000660", "name": "SK hynix"},
                {"ticker": "035420.KS", "source_code": "035420", "name": "Naver Corporation"},
                {"ticker": "035720.KS", "source_code": "035720", "name": "Kakao Corporation"},
                {"ticker": "005380.KS", "source_code": "005380", "name": "Hyundai Motor"},
            ],
        },
    ],
}


def _clean(value):
    if value is None:
        return None
    text = re.sub(r"\s+", " ", BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)).strip()
    return text or None


def _parse_dt(value):
    """Parse a timestamp to aware UTC datetime, or None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000 if value > 10**11 else value, timezone.utc)
        except (ValueError, OSError):
            return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo("Asia/Seoul"))
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _sleep(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


# Per-ticker LIHKG search keyword (Chinese name) and category title keys —
# the same values scripts/collect_hk_public.py proved work. Bare short codes
# are deliberately not used: they match unrelated numbers.
LIHKG_KEYWORDS = {"0700.HK": "騰訊", "9988.HK": "阿里", "0005.HK": "匯豐",
                  "3690.HK": "美團", "1299.HK": "友邦"}
LIHKG_TITLE_KEYS = {"0700.HK": ("騰訊", "00700"),
                    "9988.HK": ("阿里", "09988", "阿里巴巴"),
                    "0005.HK": ("匯豐", "滙豐", "00005", "HSBC"),
                    "3690.HK": ("美團", "03690"),
                    "1299.HK": ("友邦", "01299", "AIA")}
LIHKG_SEARCH_PAGES = 5
LIHKG_CATEGORY_PAGES = 5


def _lihkg_row(post: dict, ticker: str) -> dict:
    created = _parse_dt(post.get("create_time"))
    return {"ticker": ticker, "source": "LIHKG",
            "timestamp_utc": created.isoformat().replace("+00:00", "Z") if created else None,
            "text": _clean(post.get("title")), "likes": post.get("like_count"),
            "reposts": None, "views": None, "author_followers": None,
            "post_id": str(post.get("thread_id")),
            "url": f"https://lihkg.com/thread/{post.get('thread_id')}/page/1"}


def fetch_lihkg(ticker: str, code: str, keyword: str, cutoff: datetime, now: datetime,
                max_pages: int, delay: float) -> list[dict]:
    """LIHKG search API (finance category only) + finance-category listing.

    Bare requests 403 on Cloudflare; the Referer + X-Requested-With headers
    are required. Search uses the Chinese name as keyword and keeps only
    cat_id 15 (finance); the category listing is title-filtered by
    LIHKG_TITLE_KEYS. Thread titles only, not full replies.
    """
    rows: list[dict] = []
    seen: set[str] = set()
    keyword = LIHKG_KEYWORDS.get(ticker, keyword)
    headers = dict(LIHKG_HEADERS)
    headers["Referer"] = "https://lihkg.com/search?" + urlencode(
        {"q": keyword, "sort": "desc_create_time", "type": "thread"})
    for page in range(1, LIHKG_SEARCH_PAGES + 1):
        try:
            resp = requests.get(LIHKG_API, params={"q": keyword, "sort": "desc_create_time",
                                                    "type": "thread", "page": page},
                                headers=headers, timeout=30)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        for item in (resp.json().get("response", {}).get("items") or []):
            if item.get("cat_id") != 15:
                continue
            created = _parse_dt(item.get("create_time"))
            if not created or not (cutoff <= created <= now):
                continue
            thread_id = str(item.get("thread_id"))
            if thread_id in seen:
                continue
            seen.add(thread_id)
            rows.append(_lihkg_row(item, ticker))
        _sleep(delay)
    cat_headers = dict(LIHKG_HEADERS)
    cat_headers["Referer"] = "https://lihkg.com/category/15"
    keys = LIHKG_TITLE_KEYS.get(ticker, ())
    for page in range(1, LIHKG_CATEGORY_PAGES + 1):
        try:
            resp = requests.get(LIHKG_CATEGORY, params={"cat_id": 15, "page": page, "order": "now"},
                                headers=cat_headers, timeout=30)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        for item in (resp.json().get("response", {}).get("items") or []):
            title = item.get("title") or ""
            if not any(key in title for key in keys):
                continue
            created = _parse_dt(item.get("create_time"))
            if not created or not (cutoff <= created <= now):
                continue
            thread_id = str(item.get("thread_id"))
            if thread_id in seen:
                continue
            seen.add(thread_id)
            rows.append(_lihkg_row(item, ticker))
        _sleep(delay)
    return rows


def _moomoo_post(url: str, ticker: str, cutoff: datetime, now: datetime) -> dict | None:
    """Fetch one Moomoo feed page; exact publication metadata from its
    DiscussionForumPosting JSON-LD (datePublished). Returns None when the
    post is outside the window or has no usable timestamp."""
    try:
        resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    soup = BeautifulSoup(resp.text, "html.parser")
    metadata = None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            candidate = json.loads(tag.string or tag.get_text())
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and candidate.get("@type") == "DiscussionForumPosting":
            metadata = candidate
            break
    if not metadata or not metadata.get("datePublished"):
        return None
    raw_stamp = str(metadata["datePublished"])
    # Moomoo's own data can carry hour 24 (2026-11-06T24:55:38+08:00):
    # midnight of the next day, not a parse failure.
    match = re.match(r"^(\d{4}-\d{2}-\d{2})T24:(\d{2}:\d{2}(?:\.\d+)?)(.*)$", raw_stamp)
    if match:
        base = datetime.strptime(match.group(1), "%Y-%m-%d") + timedelta(days=1)
        raw_stamp = f"{base.date().isoformat()}T00:{match.group(2)}{match.group(3)}"
    stamp = _parse_dt(raw_stamp)
    if not stamp or not (cutoff <= stamp <= now):
        return None
    pid = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1].rsplit("-", 1)[-1]
    headline = metadata.get("headline", "")
    bodies = [node.get_text(" ", strip=True) for node in soup.select(".richtext-module-wrapper")]
    text = "\n".join(dict.fromkeys([headline] + bodies)).strip()
    if not text:
        return None
    likes = None
    for reaction in soup.select(".face-like-bar__item"):
        image = reaction.find("img")
        if image and image.get("alt") == "Thumbs Up":
            digits = re.sub(r"[^\d]", "", reaction.get_text(" ", strip=True))
            likes = int(digits) if digits else None
    body = soup.select_one(".feed-detail__content-wrapper")
    view_match = re.search(r"([\d,]+)\s+Views", body.get_text(" ", strip=True) if body else "")
    return {"ticker": ticker, "source": "Moomoo",
            "timestamp_utc": stamp.isoformat().replace("+00:00", "Z"),
            "text": text, "likes": likes, "reposts": None,
            "views": int(view_match.group(1).replace(",", "")) if view_match else None,
            "author_followers": None, "post_id": pid, "url": url}


def fetch_moomoo(ticker: str, code: str, cutoff: datetime, now: datetime,
                 max_pages: int, delay: float) -> list[dict]:
    """Moomoo stock community page (plain HTTP, UA-only headers).

    The page varies per request between the SSR page (with post links) and
    a 10KB JS shell; a browser-like Accept header flips it to the shell, so
    only a User-Agent is sent, with retries. Each linked feed page is then
    fetched for exact publication metadata. Best-effort: returns what the
    page exposes; an empty list is reported, never faked.
    """
    rows: list[dict] = []
    url = MOOMOO_PAGE.format(code=code)
    html = None
    for _attempt in range(5):
        try:
            resp = requests.get(url, headers={"User-Agent": BROWSER_UA}, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 100_000:
                html = resp.text
                break
        except requests.RequestException:
            pass
        _sleep(3)
    if not html:
        return rows
    soup = BeautifulSoup(html, "html.parser")
    links = list(dict.fromkeys(
        a["href"] for a in soup.select(".nnq-list-item .publish-time a[href]")
        if "/community/feed/" in a["href"]))
    for href in links[:20]:
        full = href if href.startswith("http") else "https://www.moomoo.com" + href
        row = _moomoo_post(full, ticker, cutoff, now)
        if row:
            rows.append(row)
        _sleep(0.25)
    return rows


def fetch_naver(ticker: str, code: str, cutoff: datetime, now: datetime,
                max_pages: int, delay: float) -> list[dict]:
    """Naver mobile stock discussion API, cursor pagination."""
    rows: list[dict] = []
    offset = None
    for _page in range(max_pages):
        params = {"discussionType": "domesticStock", "itemCode": code, "pageSize": 50,
                  "isHolderOnly": "false", "excludesItemNews": "false", "isItemNewsOnly": "false"}
        if offset:
            params["offset"] = offset
        try:
            resp = requests.get(NAVER_API, params=params,
                                headers={"User-Agent": BROWSER_UA}, timeout=30)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        payload = resp.json()
        result = payload.get("result") or {}
        items = result.get("posts") or []
        if not items:
            break
        for post in items:
            written = _parse_dt(post.get("writtenAt"))
            if not written or not (cutoff <= written <= now):
                continue
            if post.get("isNews") is True or post.get("postType") in ("news", "itemNews"):
                continue
            text = "\n".join(x for x in [_clean(post.get("title")),
                                         _clean(post.get("contentSwReplacedButImg")
                                                or post.get("contentSwReplaced")
                                                or post.get("content"))] if x)
            pid = str(post.get("id")) if post.get("id") is not None else None
            if not text or not pid:
                continue
            writer = post.get("writer") or {}
            rows.append({"ticker": ticker, "source": "naver_finance",
                         "timestamp_utc": written.isoformat().replace("+00:00", "Z"),
                         "text": text, "likes": post.get("recommendCount"),
                         "reposts": None, "views": post.get("viewCount"),
                         "author_followers": writer.get("followerCount"),
                         "post_id": pid,
                         "url": f"https://m.stock.naver.com/domestic/stock/{code}/discussion/{pid}"})
        offset = (payload.get("result") or {}).get("lastOffset") if isinstance(payload.get("result"), dict) else None
        if not offset:
            break
        _sleep(delay)
    return rows


def fetch_daum(ticker: str, code: str, cutoff: datetime, now: datetime,
               max_pages: int, delay: float) -> list[dict]:
    """Daum mobile finance forum API (response 10: data.posts)."""
    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        params = {"path": f"/content/debates/A{code}?page={page}&perPage=30&notice=true"}
        try:
            resp = requests.get(DAUM_API, params=params,
                                headers={"User-Agent": BROWSER_UA,
                                         "Referer": f"https://m.finance.daum.net/quotes/A{code}/talks"},
                                timeout=30)
        except requests.RequestException:
            break
        if resp.status_code != 200:
            break
        payload = resp.json()
        items = ((payload or {}).get("data") or {}).get("posts") or []
        if not items:
            break
        for post in items:
            created = _parse_dt(post.get("createdAt"))
            if not created or not (cutoff <= created <= now):
                continue
            post_id = post.get("id")
            if post_id in (None, ""):
                continue
            text = " ".join(x for x in (_clean(post.get("title")), _clean(post.get("content"))) if x)
            if not text:
                continue
            rows.append({"ticker": ticker, "source": "daum_finance",
                         "timestamp_utc": created.isoformat().replace("+00:00", "Z"),
                         "text": text, "likes": post.get("agreeCount"),
                         "reposts": None, "views": post.get("readCount"),
                         "author_followers": None, "post_id": str(post_id),
                         "url": f"https://m.finance.daum.net/quotes/A{code}/talks"})
        _sleep(delay)
    return rows


FETCHERS = {
    "LIHKG": fetch_lihkg,
    "Moomoo_Community": fetch_moomoo,
    "Naver_Finance_Stock_Discussion": fetch_naver,
    "Daum_Finance_Forum": fetch_daum,
}


def fetch_all(actor_input: dict) -> list[dict]:
    """Run every source x asset in the input; return retained rows."""
    lookback = int(actor_input.get("lookback_days", 10))
    max_posts = int(actor_input.get("max_posts_per_source_asset", 100))
    max_pages = int(actor_input.get("max_pages_per_source_asset", 3))
    delay = float(actor_input.get("minimum_request_delay_seconds", 2))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback)
    rows: list[dict] = []
    for market in actor_input.get("markets", []):
        for source in market.get("sources", []):
            fetcher = FETCHERS[source]
            for asset in market.get("assets", []):
                ticker, code = asset["ticker"], asset["source_code"]
                if source == "LIHKG":
                    got = fetcher(ticker, code, asset["name"], cutoff, now, max_pages, delay)
                else:
                    got = fetcher(ticker, code, cutoff, now, max_pages, delay)
                rows.extend(got[:max_posts])
                print(f"{ticker} {source}: {len(got)} retained", flush=True)
    return rows


async def _run_on_apify() -> None:
    from apify import Actor

    async with Actor:
        actor_input = await Actor.get_input() or {}
        merged = {**DEFAULT_INPUT, **actor_input}
        rows = fetch_all(merged)
        for row in rows:
            await Actor.push_data(row)
        Actor.log.info("Pushed %d rows to the dataset.", len(rows))


def _local_test(max_posts: int) -> int:
    rows = fetch_all(DEFAULT_INPUT)
    print(f"\nLocal test: {len(rows)} rows total "
          f"({sum(1 for r in rows if r['source'] == 'LIHKG')} LIHKG, "
          f"{sum(1 for r in rows if r['source'] == 'Moomoo')} Moomoo, "
          f"{sum(1 for r in rows if r['source'] == 'naver_finance')} Naver, "
          f"{sum(1 for r in rows if r['source'] == 'daum_finance')} Daum)")
    for row in rows[:max_posts]:
        print(json.dumps(row, ensure_ascii=False)[:300])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="cwt-public-finance-sources Actor")
    parser.add_argument("--local-test", action="store_true",
                        help="fetch the real public endpoints locally, no Apify account")
    parser.add_argument("--max-posts", type=int, default=5, help="rows to print in local test")
    args = parser.parse_args()
    if args.local_test:
        return _local_test(args.max_posts)
    import asyncio

    asyncio.run(_run_on_apify())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
