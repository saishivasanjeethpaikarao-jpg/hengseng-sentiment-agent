"""Simple self-contained HTML market summary; extracted claims require human review."""

from __future__ import annotations

import html
from pathlib import Path

import pandas as pd

from .features import aggregate_posts, deduplicate_events
from .levels import community_levels
from .sentiment import direction_from_score, score_sentiment

MARKET_CUTOFFS = {"HKEX": "16:10", "KRX": "15:40"}
LONG_TERMS = ("long", "buy", "bullish", "看多", "看好", "買入", "买入", "매수")
SHORT_TERMS = ("short", "sell", "bearish", "看空", "沽出", "賣出", "卖出", "매도")


def _position(texts: list[str]) -> str:
    long_n = short_n = 0
    for text in texts:
        lowered = str(text).lower()
        long_n += sum(lowered.count(term) for term in LONG_TERMS)
        short_n += sum(lowered.count(term) for term in SHORT_TERMS)
    if long_n == short_n == 0:
        return "Not detected"
    if long_n > short_n:
        return "Long / buy cues"
    if short_n > long_n:
        return "Short / sell cues"
    return "Mixed"


def _levels(texts: list[str], ticker: str, quote_price: float | None, currency: str = "") -> str:
    """Strict money-only support/resistance levels for one ticker.

    Shared implementation with the offline pipeline (see levels.py): bare
    numbers such as "Support 22" or "Support 5%" are rejected, so only
    money-like values near the reference price are reported.
    """
    if not texts or quote_price is None:
        return "Not detected", "Not detected"
    posts = pd.DataFrame([{"ticker": ticker, "text": t, "url": "", "source": ""}
                          for t in texts])
    quotes = pd.DataFrame([{"ticker": ticker, "price": quote_price, "currency": currency}])
    levels = community_levels(posts, quotes)
    if levels.empty:
        return "Not detected", "Not detected"
    support = levels.loc[levels["kind"].eq("support"), "level"].drop_duplicates().head(3)
    resistance = levels.loc[levels["kind"].eq("resistance"), "level"].drop_duplicates().head(3)
    return (", ".join(support) if len(support) else "Not detected",
            ", ".join(resistance) if len(resistance) else "Not detected")


def _report_rows(posts: pd.DataFrame, prices: pd.DataFrame, assets: pd.DataFrame,
                 market: str, timezone: str, cutoff: str | None = None) -> list[dict]:
    """Build the per-ticker rows for the visual report.

    Posts are aggregated with the market cutoff (HKEX 16:10, KRX 15:40 by
    default) against the price-bar session dates, so a post after the cutoff
    rolls to the next session instead of counting for a closed one.
    """
    cutoff = cutoff or MARKET_CUTOFFS.get(market, "23:59")
    market_assets = assets.loc[assets["market"].eq(market)].copy()
    local_posts = deduplicate_events(posts[posts["ticker"].isin(market_assets["ticker"])].copy(), "timestamp_utc")
    session_dates = sorted(pd.to_datetime(
        prices.get("date", pd.Series(dtype=object)), errors="coerce").dropna().dt.strftime("%Y-%m-%d").unique().tolist())
    if not local_posts.empty:
        scores = local_posts.groupby("ticker")["text"].apply(lambda s: s.map(score_sentiment).mean()).to_dict()
        texts_by_ticker = local_posts.groupby("ticker")["text"].apply(list).to_dict()
        sources = local_posts.groupby("ticker")["source"].nunique().to_dict() if "source" in local_posts else {}
        mentions = aggregate_posts(local_posts, timezone, cutoff, session_dates=session_dates or None)
        counts = mentions.groupby("ticker")["post_count"].sum().to_dict() if not mentions.empty else {}
    else:
        scores, texts_by_ticker, sources, counts = {}, {}, {}, {}

    valid_price_dates = pd.to_datetime(prices.get("date", pd.Series(dtype=object)), errors="coerce")
    report_latest_date = valid_price_dates.max() if valid_price_dates.notna().any() else pd.NaT
    rows = []
    for asset in market_assets.to_dict(orient="records"):
        ticker = asset["ticker"]
        bars = prices.loc[prices["ticker"].eq(ticker)].copy()
        bars["_date"] = pd.to_datetime(bars["date"], errors="coerce")
        bars["_close"] = pd.to_numeric(bars["close"], errors="coerce")
        bars = bars.dropna(subset=["_date", "_close"]).sort_values("_date")
        if bars.empty:
            current, price_date, staleness = None, None, None
        else:
            latest_bar = bars.iloc[-1]
            current, price_date = float(latest_bar["_close"]), latest_bar["_date"].date().isoformat()
            staleness = int((report_latest_date - latest_bar["_date"]).days) if pd.notna(report_latest_date) else None
        score = float(scores.get(ticker, 0.0))
        texts = texts_by_ticker.get(ticker, [])
        support, resistance = _levels(texts, ticker, current, str(asset.get("currency", "")))
        rows.append({"ticker": ticker, "asset_name": asset.get("asset_name", ticker), "currency": asset.get("currency", ""),
                     "price": current, "price_date": price_date, "price_staleness_days": staleness,
                     "mentions": int(counts.get(ticker, 0)), "sentiment": score, "direction": direction_from_score(score),
                     "position": _position(texts), "support": support, "resistance": resistance,
                     "sources": int(sources.get(ticker, 0))})
    rows.sort(key=lambda row: (-row["mentions"], -row["sentiment"], row["ticker"]), reverse=False)
    return rows


def generate_visual_report(posts: pd.DataFrame, prices: pd.DataFrame, assets: pd.DataFrame,
                           market: str, timezone: str, output: str | Path,
                           cutoff: str | None = None) -> Path:
    rows = _report_rows(posts, prices, assets, market, timezone, cutoff)
    max_mentions = max([r["mentions"] for r in rows] + [1])
    row_html = []
    for r in rows:
        price = "—" if r["price"] is None else f"{r['price']:,.2f} {html.escape(str(r['currency']))}".strip()
        if r["price_date"]:
            stale = f"; {r['price_staleness_days']} days stale" if r["price_staleness_days"] else ""
            price += f"<small>As of {html.escape(r['price_date'])}{stale}</small>"
        bar_width = int(100 * r["mentions"] / max_mentions)
        color = "#21865b" if r["sentiment"] > 0.1 else "#bd4551" if r["sentiment"] < -0.1 else "#7b8492"
        row_html.append("<tr>" + f"<td><b>{html.escape(r['ticker'])}</b><small>{html.escape(str(r['asset_name']))}</small></td>" +
                        f"<td>{price}</td><td>{r['mentions']}<div class='bar'><i style='width:{bar_width}%'></i></div></td>" +
                        f"<td style='color:{color}'>{r['sentiment']:+.3f}<small>{r['direction']}</small></td>" +
                        f"<td>{html.escape(r['position'])}</td><td>{html.escape(r['support'])}</td>" +
                        f"<td>{html.escape(r['resistance'])}</td><td>{r['sources']}</td></tr>")
    title = f"{market} sentiment snapshot"
    page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)}</title><style>body{{font:15px system-ui,-apple-system,Segoe UI,sans-serif;background:#f4f6fa;color:#182033;margin:0;padding:24px}}main{{max-width:1200px;margin:auto}}h1{{margin-bottom:4px}}.sub{{color:#5d6678;margin:0 0 18px}}.card{{background:white;border:1px solid #e1e5ee;border-radius:12px;padding:16px;overflow-x:auto}}table{{border-collapse:collapse;width:100%;min-width:900px}}th,td{{padding:12px 10px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:top}}th{{font-size:12px;color:#687287;text-transform:uppercase}}small{{display:block;color:#6a7383;margin-top:3px}}.bar{{height:5px;background:#eef0f5;border-radius:4px;margin-top:5px;min-width:65px}}.bar i{{display:block;background:#5b78d1;height:100%;border-radius:4px}}.note{{font-size:13px;color:#5d6678;line-height:1.5;margin-top:14px}}</style></head><body><main><h1>{html.escape(title)}</h1><p class='sub'>Sorted by social mentions, then baseline sentiment. Prices are sorted by date and show their as-of date and staleness.</p><div class='card'><table><thead><tr><th>Asset</th><th>Current price</th><th>Mentions</th><th>Sentiment / direction</th><th>Position cues</th><th>Support cues</th><th>Resistance cues</th><th>Sources</th></tr></thead><tbody>{''.join(row_html)}</tbody></table></div><p class='note'>Local market timezone: {html.escape(timezone)}. Sentiment and position are keyword-baseline signals; support/resistance values are regex-extracted community claims and may be wrong. Missing follower and engagement telemetry is not treated as observed zero. This is not financial advice. Review source posts before relying on any extracted cue.</p></main></body></html>"""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output
