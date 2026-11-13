"""Simple self-contained HTML market summary; extracted claims require human review."""

from __future__ import annotations

import html
import re
from pathlib import Path

import pandas as pd

from .features import aggregate_posts
from .sentiment import direction_from_score, score_sentiment

SUPPORT_RE = re.compile(r"(?:support|支撑|支撐|지지)[^\d]{0,18}([0-9][0-9,]*(?:\.\d+)?)", re.IGNORECASE)
RESISTANCE_RE = re.compile(r"(?:resistance|阻力|阻力位|저항)[^\d]{0,18}([0-9][0-9,]*(?:\.\d+)?)", re.IGNORECASE)
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


def _levels(texts: list[str], pattern: re.Pattern) -> str:
    values = []
    for text in texts:
        values.extend(match.replace(",", "") for match in pattern.findall(str(text)))
    unique = list(dict.fromkeys(values))
    return ", ".join(unique[:3]) if unique else "Not detected"


def generate_visual_report(posts: pd.DataFrame, prices: pd.DataFrame, assets: pd.DataFrame,
                           market: str, timezone: str, output: str | Path) -> Path:
    market_assets = assets.loc[assets["market"].eq(market)].copy()
    local_posts = posts[posts["ticker"].isin(market_assets["ticker"])].copy()
    if not local_posts.empty:
        scores = local_posts.groupby("ticker")["text"].apply(lambda s: s.map(score_sentiment).mean()).to_dict()
        texts_by_ticker = local_posts.groupby("ticker")["text"].apply(list).to_dict()
        sources = local_posts.groupby("ticker")["source"].nunique().to_dict() if "source" in local_posts else {}
        # Count all collected posts for the report; this is not the prediction feature cutoff.
        mentions = aggregate_posts(local_posts, timezone, "23:59")
        counts = mentions.groupby("ticker")["post_count"].sum().to_dict() if not mentions.empty else {}
    else:
        scores, texts_by_ticker, sources, counts = {}, {}, {}, {}

    rows = []
    for asset in market_assets.to_dict(orient="records"):
        ticker = asset["ticker"]
        bars = prices.loc[prices["ticker"].eq(ticker)].copy()
        current = pd.to_numeric(bars["close"], errors="coerce").dropna().iloc[-1] if not bars.empty and pd.to_numeric(bars["close"], errors="coerce").notna().any() else None
        score = float(scores.get(ticker, 0.0))
        texts = texts_by_ticker.get(ticker, [])
        rows.append({
            "ticker": ticker,
            "asset_name": asset.get("asset_name", ticker),
            "currency": asset.get("currency", ""),
            "price": current,
            "mentions": int(counts.get(ticker, 0)),
            "sentiment": score,
            "direction": direction_from_score(score),
            "position": _position(texts),
            "support": _levels(texts, SUPPORT_RE),
            "resistance": _levels(texts, RESISTANCE_RE),
            "sources": int(sources.get(ticker, 0)),
        })
    rows.sort(key=lambda row: (-row["mentions"], -row["sentiment"], row["ticker"]), reverse=False)
    max_mentions = max([r["mentions"] for r in rows] + [1])
    row_html = []
    for r in rows:
        price = "—" if r["price"] is None else f"{r['price']:,.2f} {html.escape(str(r['currency']))}".strip()
        bar_width = int(100 * r["mentions"] / max_mentions)
        color = "#21865b" if r["sentiment"] > 0.1 else "#bd4551" if r["sentiment"] < -0.1 else "#7b8492"
        row_html.append(
            "<tr>" +
            f"<td><b>{html.escape(r['ticker'])}</b><small>{html.escape(str(r['asset_name']))}</small></td>" +
            f"<td>{price}</td><td>{r['mentions']}<div class='bar'><i style='width:{bar_width}%'></i></div></td>" +
            f"<td style='color:{color}'>{r['sentiment']:+.3f}<small>{r['direction']}</small></td>" +
            f"<td>{html.escape(r['position'])}</td><td>{html.escape(r['support'])}</td>" +
            f"<td>{html.escape(r['resistance'])}</td><td>{r['sources']}</td></tr>"
        )
    title = f"{market} sentiment snapshot"
    page = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(title)}</title><style>
body{{font:15px system-ui,-apple-system,Segoe UI,sans-serif;background:#f4f6fa;color:#182033;margin:0;padding:24px}}
main{{max-width:1200px;margin:auto}}h1{{margin-bottom:4px}}.sub{{color:#5d6678;margin:0 0 18px}}
.card{{background:white;border:1px solid #e1e5ee;border-radius:12px;padding:16px;overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:900px}}th,td{{padding:12px 10px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:top}}th{{font-size:12px;color:#687287;text-transform:uppercase}}small{{display:block;color:#6a7383;margin-top:3px}}.bar{{height:5px;background:#eef0f5;border-radius:4px;margin-top:5px;min-width:65px}}.bar i{{display:block;background:#5b78d1;height:100%;border-radius:4px}}
.note{{font-size:13px;color:#5d6678;line-height:1.5;margin-top:14px}}
</style></head><body><main><h1>{html.escape(title)}</h1><p class='sub'>Sorted by social mentions, then baseline sentiment. Prices are the latest rows in the supplied price file.</p>
<div class='card'><table><thead><tr><th>Asset</th><th>Current price</th><th>Mentions</th><th>Sentiment / direction</th><th>Position cues</th><th>Support cues</th><th>Resistance cues</th><th>Sources</th></tr></thead><tbody>{''.join(row_html)}</tbody></table></div>
<p class='note'>Local market timezone: {html.escape(timezone)}. Sentiment and position are keyword-baseline signals; support/resistance values are regex-extracted community claims and may be wrong. This is not financial advice. Review source posts before relying on any extracted cue.</p>
</main></body></html>"""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    return output
