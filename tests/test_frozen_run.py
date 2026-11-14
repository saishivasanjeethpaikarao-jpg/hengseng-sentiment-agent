"""Frozen-run package checks (Fix 4).

docs/frozen-run-2026-11-14/ must keep a valid SHA-256 manifest and its
summary.json must agree with the live reports/real_run/summary.json (the
run that produced the frozen numbers). The full end-to-end reproduction —
temp-copy the repo, restore the frozen data, re-run the pipeline, diff the
MAEs — lives in scripts/verify_frozen_run.py --reproduce and was run
2026-11-14 with a clean pass; it is too slow to run in the unit suite.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_frozen_run import MAE_PATHS, verify_manifest  # noqa: E402

PKG = ROOT / "docs" / "frozen-run-2026-11-14"


def _get(summary: dict, keys: tuple[str, ...]):
    value = summary
    for key in keys:
        value = value[key]
    return value


def test_frozen_manifest_valid():
    assert verify_manifest() == []


def test_frozen_summary_matches_live_run():
    frozen = json.loads((PKG / "reports" / "summary.json").read_text(encoding="utf-8"))
    live = json.loads((ROOT / "reports" / "real_run" / "summary.json").read_text(encoding="utf-8"))
    for keys in MAE_PATHS:
        assert abs(float(_get(frozen, keys)) - float(_get(live, keys))) <= 1e-9, ".".join(keys)
    for key in ("posts", "news", "prices_rows"):
        assert frozen[key] == live[key], key
