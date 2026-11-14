"""Render a compact MAE comparison from the aggregate real-run summary.

The summary and row-level run outputs are intentionally not committed. After a
local run has produced reports/real_run/summary.json, this script regenerates
the aggregate README chart without reading individual social-post text.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "reports" / "real_run" / "summary.json"
DEFAULT_OUTPUT = ROOT / "docs" / "frozen-run-mae-comparison.png"


def render(summary_path: Path, output_path: Path) -> Path:
    """Render long-history and short sentiment-pilot MAE comparisons."""
    models = json.loads(summary_path.read_text(encoding="utf-8"))["models"]
    markets = ["HKEX", "KRX"]

    blue = "#4868B8"       # price-only Ridge
    teal = "#44A694"       # sentiment Ridge in the short pilot
    pale = "#B4BFD7"       # zero-return reference
    ink = "#182033"
    muted = "#5D6678"

    fig, axes = plt.subplots(
        1, 2, figsize=(14, 6.3), gridspec_kw={"width_ratios": [1, 1.25]}
    )
    fig.patch.set_facecolor("#F4F6FA")
    for ax in axes:
        ax.set_facecolor("#FFFFFF")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color("#DCE2EC")
        ax.grid(axis="y", color="#E7EBF2", linewidth=0.8)
        ax.set_axisbelow(True)
        ax.tick_params(colors=muted, labelsize=10, length=0)

    # Long-history price-only benchmark.
    price_mae = [100 * models[m]["price_only_oos"]["mae_return"] for m in markets]
    zero_mae = [100 * models[m]["price_only_oos"]["zero_baseline_mae"] for m in markets]
    row_counts = [models[m]["price_only_oos"]["n_test"] for m in markets]
    date_counts = [models[m]["price_only_oos"]["test_dates"] for m in markets]
    x = np.arange(len(markets))
    width = 0.32
    bars_price = axes[0].bar(
        x - width / 2, price_mae, width, color=blue, label="Price-only Ridge", zorder=3
    )
    bars_zero = axes[0].bar(
        x + width / 2, zero_mae, width, color=pale, label="Zero-return baseline", zorder=3
    )
    axes[0].set_title(
        "A  Long-history price benchmark", loc="left", color=ink,
        fontsize=14, fontweight="bold", pad=14,
    )
    axes[0].set_ylabel("Mean absolute log-return error (MAE, %)", color=muted, fontsize=10)
    axes[0].set_xticks(
        x,
        [f"{m}\n{n:,} predictions · {d} dates" for m, n, d in zip(markets, row_counts, date_counts)],
    )
    axes[0].set_ylim(0, 3.35)
    for bars in (bars_price, bars_zero):
        axes[0].bar_label(bars, fmt="%.3f", padding=4, fontsize=9, color=ink)
    axes[0].text(
        0.02, 0.96, "Price features only — not a long-history sentiment test",
        transform=axes[0].transAxes, va="top", color=muted, fontsize=9,
    )

    # Short sentiment pilot and same-window comparators. Row/date counts come
    # from the summary, never hardcoded: a later run with a different pilot
    # size must not render stale labels. If the pilot was not evaluated
    # (too few social sessions), the panel states that instead of plotting.
    pilot = [models[m]["short_sentiment_experiment"] for m in markets]
    pilot_evaluated = all("metrics" in p for p in pilot)
    pilot_labels = []
    for m, p in zip(markets, pilot):
        if "metrics" in p:
            pilot_labels.append(
                f"{m}\n{p['metrics']['n_test']} rows · {p['metrics']['test_dates']} dates")
        else:
            pilot_labels.append(f"{m}\nnot evaluated")
    if pilot_evaluated:
        series = [
            (
                "Sentiment Ridge", teal,
                [100 * models[m]["short_sentiment_experiment"]["metrics"]["mae_return"] for m in markets],
            ),
            (
                "Price-only Ridge", blue,
                [100 * models[m]["short_sentiment_experiment"]["paired_price_only_metrics"]["mae_return"] for m in markets],
            ),
            (
                "Zero-return baseline", pale,
                [100 * models[m]["short_sentiment_experiment"]["metrics"]["zero_baseline_mae"] for m in markets],
            ),
        ]
    else:
        series = []
    x_pilot = np.arange(len(markets))
    pilot_width = 0.23
    all_bars = []
    for i, (name, color, values) in enumerate(series):
        bars = axes[1].bar(
            x_pilot + (i - 1) * pilot_width, values, pilot_width,
            color=color, label=name, zorder=3,
        )
        all_bars.append(bars)
    axes[1].set_title(
        "B  Sentiment pilot — exploratory only", loc="left", color=ink,
        fontsize=14, fontweight="bold", pad=14,
    )
    axes[1].set_ylabel("Mean absolute log-return error (MAE, %)", color=muted, fontsize=10)
    axes[1].set_xticks(x_pilot, pilot_labels)
    axes[1].set_ylim(0, 6.4)
    if not pilot_evaluated:
        axes[1].text(0.5, 0.5, "Pilot not evaluated:\ntoo few social sessions\nin this run",
                     transform=axes[1].transAxes, ha="center", va="center",
                     color=muted, fontsize=11)
    for bars in all_bars:
        axes[1].bar_label(bars, fmt="%.3f", padding=4, fontsize=8.5, color=ink)
    axes[1].text(
        0.02, 0.96, "Only a few held-out dates per market; not enough to infer an edge",
        transform=axes[1].transAxes, va="top", color=muted, fontsize=9,
    )

    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", bbox_to_anchor=(0.5, 0.91),
               ncol=3, frameon=False, fontsize=9)
    fig.suptitle(
        "What the frozen run actually shows", x=0.06, y=0.99, ha="left",
        fontsize=19, fontweight="bold", color=ink,
    )
    pilot_note = (
        "The tiny sentiment run beats its paired price-only Ridge, but still loses to no change. "
        if pilot_evaluated else
        "The sentiment pilot was not evaluated in this run (too few social sessions). "
    )
    fig.text(
        0.06, 0.025,
        "Lower is better. Long-history Ridge slightly loses to no change in both markets. "
        + pilot_note +
        "No predictive edge is established.",
        color=muted, fontsize=9.5, wrap=True,
    )
    fig.tight_layout(rect=[0.035, 0.085, 0.98, 0.85], w_pad=2.2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180, facecolor=fig.get_facecolor(), bbox_inches="tight")
    plt.close(fig)
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY,
                        help=f"aggregate run summary (default: {DEFAULT_SUMMARY})")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"output PNG (default: {DEFAULT_OUTPUT})")
    args = parser.parse_args()
    if not args.summary.is_file():
        parser.error(f"summary file not found: {args.summary}; run the real-data pipeline first")
    print(render(args.summary, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
