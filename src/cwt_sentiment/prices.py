"""Optional market-price adapter; use an approved/licensed provider if required by the reviewer."""

from __future__ import annotations

import pandas as pd


def download_yahoo_prices(assets: pd.DataFrame, period: str = "1y") -> pd.DataFrame:
    """Fetch daily bars for each configured symbol using yfinance.

    Yahoo Finance availability/terms can vary by market and symbol. This is a convenient
    prototype adapter, not an assignment-mandated provider or a substitute for licensed data.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install the project with pip install -e '.[dev,prices]' to fetch prices.") from exc
    rows = []
    failures = []
    for item in assets.to_dict(orient="records"):
        ticker = str(item["ticker"])
        history = yf.Ticker(ticker).history(period=period, auto_adjust=False, actions=False)
        if history.empty:
            failures.append(ticker)
            continue
        history = history.reset_index()
        date_column = "Date" if "Date" in history else history.columns[0]
        for record in history.to_dict(orient="records"):
            rows.append({
                "ticker": ticker,
                "date": pd.Timestamp(record[date_column]).strftime("%Y-%m-%d"),
                "open": record.get("Open"),
                "high": record.get("High"),
                "low": record.get("Low"),
                "close": record.get("Close"),
                "volume": record.get("Volume"),
                "currency": item.get("currency", ""),
                "data_source": "Yahoo Finance via yfinance",
            })
    if not rows:
        raise RuntimeError(f"No price bars returned. Unavailable symbols: {', '.join(failures) or 'all'}")
    if failures:
        print(f"Warning: no bars returned for: {', '.join(failures)}")
    return pd.DataFrame(rows).sort_values(["ticker", "date"]).reset_index(drop=True)
