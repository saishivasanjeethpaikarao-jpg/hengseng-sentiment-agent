"""Command-line entry points for a reproducible starter run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

from .collectors import exa_news_for_assets, normalize_social_rows, run_apify_actor
from .features import build_training_frame
from .model import evaluate_oos, forecast_latest
from .prices import download_yahoo_prices
from .report import generate_visual_report


def _read_optional_csv(path: str | None, columns: list[str]) -> pd.DataFrame:
    return pd.read_csv(path) if path and Path(path).exists() else pd.DataFrame(columns=columns)


def _parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cwt-sentiment", description="HKEX/KRX sentiment research starter")
    sub = parser.add_subparsers(dest="command", required=True)

    apify = sub.add_parser("apify-pull", help="Run an Apify actor and save raw JSON")
    apify.add_argument("--actor-id", required=True)
    apify.add_argument("--input", required=True, help="JSON matching this actor's own input schema")
    apify.add_argument("--max-total-charge-usd", type=float, default=0.0,
                       help="Hard cap for this run; defaults to $0.00. Raise only after approving a budget.")
    apify.add_argument("--max-items", type=int, default=100,
                       help="Maximum billable results for pay-per-result actors, where supported.")
    apify.add_argument("--out", required=True)

    normalize = sub.add_parser("normalize-social", help="Map a raw actor JSON list to canonical posts CSV")
    normalize.add_argument("--raw", required=True)
    normalize.add_argument("--source", required=True)
    normalize.add_argument("--ticker", required=True)
    normalize.add_argument("--field-map", help="Optional JSON object mapping canonical field names to actor keys")
    normalize.add_argument("--out", required=True)

    exa = sub.add_parser("exa-pull", help="Fetch recent Exa news for assets from a CSV")
    exa.add_argument("--assets", required=True)
    exa.add_argument("--market", help="Optional market filter, e.g. HKEX or KRX")
    exa.add_argument("--days", type=int, default=10)
    exa.add_argument("--num-results", type=int, default=8)
    exa.add_argument("--confirm-exa-free-balance-and-auto-recharge-off", action="store_true",
                     help="Confirm in Exa's dashboard that free credits remain and auto-recharge is disabled.")
    exa.add_argument("--out", required=True)

    prices = sub.add_parser("prices-pull", help="Optionally fetch daily bars via Yahoo Finance/yfinance")
    prices.add_argument("--assets", required=True)
    prices.add_argument("--market", help="Optional market filter")
    prices.add_argument("--period", default="1y", help="yfinance history period, such as 6mo, 1y, 2y")
    prices.add_argument("--out", required=True)

    build = sub.add_parser("build", help="Build session-aligned features and next-session labels")
    build.add_argument("--posts", required=True)
    build.add_argument("--news")
    build.add_argument("--prices", required=True)
    build.add_argument("--timezone", required=True)
    build.add_argument("--cutoff", required=True, help="Local HH:MM prediction cutoff")
    build.add_argument("--out", required=True)

    evaluate = sub.add_parser("evaluate", help="Run expanding chronological out-of-sample evaluation")
    evaluate.add_argument("--features", required=True)
    evaluate.add_argument("--splits", type=int, default=4)
    evaluate.add_argument("--metrics-out", required=True)
    evaluate.add_argument("--predictions-out", required=True)

    forecast = sub.add_parser("forecast", help="Fit on labeled history and forecast each ticker's latest row")
    forecast.add_argument("--features", required=True)
    forecast.add_argument("--out", required=True)

    report = sub.add_parser("report", help="Create a sortable visual HTML report for one exchange")
    report.add_argument("--posts", required=True)
    report.add_argument("--prices", required=True)
    report.add_argument("--assets", required=True)
    report.add_argument("--market", required=True)
    report.add_argument("--timezone", required=True)
    report.add_argument("--out", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    if args.command == "apify-pull":
        actor_input = json.loads(Path(args.input).read_text(encoding="utf-8"))
        result = run_apify_actor(
            args.actor_id, actor_input, max_total_charge_usd=args.max_total_charge_usd, max_items=args.max_items
        )
        _parent(args.out)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(result)} raw actor records to {args.out}; run charge cap: ${args.max_total_charge_usd:.2f}.")
    elif args.command == "normalize-social":
        raw = json.loads(Path(args.raw).read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Raw Apify output must be a JSON list of records.")
        mapping = json.loads(Path(args.field_map).read_text(encoding="utf-8")) if args.field_map else None
        result = normalize_social_rows(raw, args.source, args.ticker, mapping)
        _parent(args.out)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Saved {len(result)} raw actor records to {args.out}; run charge cap: ${args.max_total_charge_usd:.2f}.")
    elif args.command == "exa-pull":
        if not args.confirm_exa_free_balance_and_auto_recharge_off:
            raise SystemExit(
                "Exa request blocked: confirm in the Exa dashboard that free credits remain and auto-recharge is off."
            )
        assets = pd.read_csv(args.assets)
        if args.market:
            assets = assets.loc[assets["market"].eq(args.market)]
        result = exa_news_for_assets(
            assets, days=args.days, num_results=args.num_results, confirm_free_only=True
        )
        _parent(args.out)
        result.to_csv(args.out, index=False)
        print(f"Saved {len(result)} news records to {args.out}.")
    elif args.command == "prices-pull":
        assets = pd.read_csv(args.assets)
        if args.market:
            assets = assets.loc[assets["market"].eq(args.market)]
        result = download_yahoo_prices(assets, period=args.period)
        _parent(args.out)
        result.to_csv(args.out, index=False)
        print(f"Saved {len(result)} price bars to {args.out}; verify data quality and provider terms.")
    elif args.command == "build":
        posts = _read_optional_csv(args.posts, ["ticker", "source", "timestamp_utc", "text"])
        news = _read_optional_csv(args.news, ["ticker", "published_at_utc", "title", "text"])
        prices = pd.read_csv(args.prices)
        result = build_training_frame(prices, posts, news, args.timezone, args.cutoff)
        _parent(args.out)
        result.to_csv(args.out, index=False)
        print(f"Wrote {len(result)} asset/session rows to {args.out}.")
    elif args.command == "evaluate":
        frame = pd.read_csv(args.features)
        metrics, predictions = evaluate_oos(frame, n_splits=args.splits)
        _parent(args.metrics_out)
        _parent(args.predictions_out)
        metrics.to_csv(args.metrics_out, index=False)
        predictions.to_csv(args.predictions_out, index=False)
        print(metrics.to_string(index=False))
        print(f"Metrics: {args.metrics_out}; predictions: {args.predictions_out}")
    elif args.command == "forecast":
        frame = pd.read_csv(args.features)
        result = forecast_latest(frame)
        _parent(args.out)
        result.to_csv(args.out, index=False)
        print(result.to_string(index=False))
        print(f"Forecast: {args.out}")
    elif args.command == "report":
        posts = _read_optional_csv(args.posts, ["ticker", "source", "timestamp_utc", "text"])
        prices = pd.read_csv(args.prices)
        assets = pd.read_csv(args.assets)
        result = generate_visual_report(posts, prices, assets, args.market, args.timezone, args.out)
        print(f"HTML report: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
