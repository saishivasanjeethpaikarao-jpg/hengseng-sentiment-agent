"""Small API adapters. Actor schemas and source-specific permissions must be verified."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import pandas as pd
import requests

POST_COLUMNS = ["ticker", "source", "timestamp_utc", "text", "likes", "reposts", "views", "author_followers", "post_id", "url"]


def run_apify_actor(actor_id: str, actor_input: dict, token: str | None = None, timeout: int = 300,
                    max_total_charge_usd: float = 0.0, max_items: int = 100):
    """Run an actor, applying an explicit total-charge cap (zero by default)."""
    token = token or os.getenv("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError("Set APIFY_API_TOKEN in the environment before Apify collection.")
    endpoint = f"https://api.apify.com/v2/acts/{quote(actor_id, safe='~')}/run-sync-get-dataset-items"
    response = requests.post(
        endpoint,
        headers={"Authorization": f"Bearer {token}"},
        params={"maxTotalChargeUsd": max_total_charge_usd, "maxItems": max_items},
        json=actor_input,
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("Expected Apify dataset-items endpoint to return a JSON list.")
    return payload


def _first(item: dict, candidates: tuple[str, ...], override: str | None = None):
    if override and override in item:
        return item.get(override)
    for key in candidates:
        if key in item and item[key] is not None:
            return item[key]
    return None


def _parse_count(value):
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("+", "")
        if not text:
            return None
        multiplier = 1
        if text[-1:].upper() in {"K", "M", "B"}:
            multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[text[-1].upper()]
            text = text[:-1]
        try:
            return float(text) * multiplier
        except ValueError:
            return None
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def normalize_social_rows(items: list[dict], source: str, ticker: str,
                          field_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Map common LIHKG/Telegram/community actor fields into the canonical post schema.

    Use field_map to override keys when a selected actor uses a different schema. Rows are
    retained even if timestamps are missing so coverage problems can be measured downstream.
    """
    field_map = field_map or {}
    aliases = {
        "timestamp_utc": ("timestamp_utc", "created_at", "dateISO", "datetime", "date", "published_at"),
        "text": ("own_text", "text", "content", "title", "message"),
        "likes": ("likes", "like_count", "likeCount", "likesCount"),
        "reposts": ("reposts", "forwards", "forward_count", "shares"),
        "views": ("views", "viewCountParsed", "viewCount", "views_count"),
        "author_followers": ("author_followers", "followers", "followerCount", "authorFollowerCount"),
        "post_id": ("post_id", "reply_id", "thread_id", "messageId", "id"),
        "url": ("url", "thread_url", "messageUrl", "link"),
    }
    rows = []
    for item in items:
        row = {"ticker": item.get("ticker") or ticker, "source": item.get("source") or source}
        for field, keys in aliases.items():
            value = _first(item, keys, field_map.get(field))
            if field == "timestamp_utc" and value:
                parsed = pd.to_datetime(value, utc=True, errors="coerce")
                value = None if pd.isna(parsed) else parsed.isoformat()
            row[field] = value
        row["text"] = "" if row.get("text") is None else str(row["text"])
        for field in ("likes", "reposts", "views", "author_followers"):
            row[field] = _parse_count(row.get(field))
        rows.append(row)
    return pd.DataFrame(rows, columns=POST_COLUMNS)


def search_exa(query: str, api_key: str | None = None, days: int = 10, num_results: int = 10,
               confirm_free_only: bool = False):
    if not confirm_free_only:
        raise RuntimeError("Exa calls are disabled until you confirm free credits remain and auto-recharge is off.")
    api_key = api_key or os.getenv("EXA_API_KEY")
    if not api_key:
        raise RuntimeError("Set EXA_API_KEY in the environment before Exa collection.")
    start = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds").replace("+00:00", "Z")
    response = requests.post(
        "https://api.exa.ai/search",
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json={
            "query": query,
            "type": "auto",
            "numResults": num_results,
            "startPublishedDate": start,
            "contents": {"text": {"maxCharacters": 2500}},
        },
        timeout=45,
    )
    response.raise_for_status()
    result = response.json()
    rows = []
    for item in result.get("results", []):
        rows.append({
            "ticker": "",  # Caller attaches the ticker used in the query.
            "published_at_utc": item.get("publishedDate") or item.get("published_date"),
            "title": item.get("title", ""),
            "text": item.get("text", "") or "",
            "url": item.get("url", ""),
            "source": item.get("author", "Exa") or "Exa",
        })
    return rows


def exa_news_for_assets(assets: pd.DataFrame, days: int = 10, num_results: int = 8,
                        confirm_free_only: bool = False) -> pd.DataFrame:
    rows = []
    for row in assets.to_dict(orient="records"):
        ticker, name = row["ticker"], row["asset_name"]
        query = f'"{name}" OR "{ticker}" stock news'
        for item in search_exa(query, days=days, num_results=num_results, confirm_free_only=confirm_free_only):
            item["ticker"] = ticker
            item["asset_name"] = name
            rows.append(item)
    return pd.DataFrame(rows, columns=["ticker", "asset_name", "published_at_utc", "title", "text", "url", "source"])
