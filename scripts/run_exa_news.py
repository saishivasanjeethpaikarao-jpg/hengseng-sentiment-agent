#!/usr/bin/env python3
"""Fetch recent Exa news for the configured assets and keep request/response logs.

Requires EXA_API_KEY in the environment. Before running, confirm in the Exa
dashboard (https://dashboard.exa.ai) that free credits remain and
auto-recharge is OFF, then pass --confirm-free-balance-and-auto-recharge-off.
No key is ever written to disk: request logs record the query and counts,
response logs record the returned items (which are public news data).

Usage:
    EXA_API_KEY=... python scripts/run_exa_news.py \
        --confirm-free-balance-and-auto-recharge-off
    python scripts/run_exa_news.py --dry-run   # print what would be called
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cwt_sentiment.collectors import exa_news_for_assets  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "exa"


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", default=str(ROOT / "config" / "assets.csv"))
    parser.add_argument("--days", type=int, default=10)
    parser.add_argument("--num-results", type=int, default=8)
    parser.add_argument("--confirm-free-balance-and-auto-recharge-off", action="store_true",
                        help="Confirm in the Exa dashboard that free credits remain and auto-recharge is off.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the queries that would be sent; make no request.")
    args = parser.parse_args()

    assets = pd.read_csv(args.assets)
    queries = [f'"{row["asset_name"]}" OR "{row["ticker"]}" stock news'
               for row in assets.to_dict(orient="records")]
    print(f"Exa news pull: {len(queries)} queries (one per ticker), "
          f"up to {args.num_results} results each, last {args.days} days.")
    for query in queries:
        print("  query:", query)
    if args.dry_run:
        print("Dry run only: no request made, no key needed.")
        return 0
    if not args.confirm_free_balance_and_auto_recharge_off:
        print("Refused: confirm in the Exa dashboard that free credits remain "
              "and auto-recharge is off, then re-run with "
              "--confirm-free-balance-and-auto-recharge-off.", file=sys.stderr)
        return 2
    if not os.getenv("EXA_API_KEY"):
        print("Refused: EXA_API_KEY is not set in the environment. Get it from "
              "the Exa dashboard (https://dashboard.exa.ai/api-keys) and export "
              "it; never paste it into a file or chat.", file=sys.stderr)
        return 2

    started = datetime.now(timezone.utc)
    result = exa_news_for_assets(assets, days=args.days, num_results=args.num_results,
                                 confirm_free_only=True)
    OUT.mkdir(parents=True, exist_ok=True)
    finished = datetime.now(timezone.utc)
    result.to_csv(OUT / "exa_news.csv", index=False)
    log = {
        "retrieved_at_utc": iso(started),
        "finished_at_utc": iso(finished),
        "provider": "Exa (exa.ai/search)",
        "queries": queries,
        "days": args.days,
        "num_results_requested": args.num_results,
        "total_records": len(result),
        "records_by_ticker": result.groupby("ticker").size().to_dict() if len(result) else {},
        "note": "API key is not recorded here. Response items are public news data.",
    }
    (OUT / "exa_request_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=2),
                                              encoding="utf-8")
    print(f"Saved {len(result)} Exa news records to {OUT / 'exa_news.csv'}")
    print(json.dumps(log, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
