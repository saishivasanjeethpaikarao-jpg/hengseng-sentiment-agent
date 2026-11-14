"""Verify the frozen 2026-11-14 run package (Fix 4).

Usage:
    python scripts/verify_frozen_run.py            # manifest check only
    python scripts/verify_frozen_run.py --reproduce  # + full pipeline re-run

The manifest check hashes every file listed in
docs/frozen-run-2026-11-14/MANIFEST.sha256. The reproduce check copies the
repo (without .venv/.git/data/reports) to a temp dir, restores the frozen
CSVs into its data/normalized/, runs run_real_pipeline.py there, and diffs
the resulting MAEs against the frozen summary.json. Your working data/ and
reports/ are never touched. Exit code 0 means the frozen MAEs reproduce.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "docs" / "frozen-run-2026-11-14"
MANIFEST = PKG / "MANIFEST.sha256"

# MAEs that must match exactly (to 1e-9) between the frozen summary and a
# re-run from the frozen data.
MAE_PATHS = [
    ("models", "HKEX", "price_only_oos", "mae_return"),
    ("models", "HKEX", "price_only_oos", "zero_baseline_mae"),
    ("models", "KRX", "price_only_oos", "mae_return"),
    ("models", "KRX", "price_only_oos", "zero_baseline_mae"),
    ("models", "HKEX", "short_sentiment_experiment", "metrics", "mae_return"),
    ("models", "KRX", "short_sentiment_experiment", "metrics", "mae_return"),
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest() -> list[str]:
    """Return a list of problems (empty = manifest matches)."""
    problems: list[str] = []
    if not MANIFEST.exists():
        return ["MANIFEST.sha256 is missing"]
    listed: set[str] = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(None, 1)
        rel = rel.lstrip("*")
        listed.add(rel)
        path = PKG / rel
        if not path.exists():
            problems.append(f"missing file: {rel}")
        elif _sha256(path) != digest:
            problems.append(f"hash mismatch: {rel}")
    # Files present but not in the manifest.
    for path in sorted(PKG.rglob("*")):
        if path.is_file() and path.name != "MANIFEST.sha256":
            rel = str(path.relative_to(PKG))
            if rel not in listed:
                problems.append(f"unlisted file: {rel}")
    return problems


def _get(summary: dict, keys: tuple[str, ...]):
    value = summary
    for key in keys:
        value = value[key]
    return value


def reproduce() -> list[str]:
    """Re-run the pipeline from the frozen data in a temp copy; return problems."""
    problems: list[str] = []
    frozen = json.loads((PKG / "reports" / "summary.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="cwt-frozen-verify-") as tmp:
        dest = Path(tmp) / "repo"
        ignore = shutil.ignore_patterns(".git", ".venv", ".pip-tmp", "data", "reports", "__pycache__")
        shutil.copytree(ROOT, dest, ignore=ignore)
        data_dir = dest / "data" / "normalized"
        data_dir.mkdir(parents=True, exist_ok=True)
        for csv_path in (PKG / "data").glob("*.csv"):
            shutil.copy(csv_path, data_dir / csv_path.name)
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(dest)
        proc = subprocess.run(
            [sys.executable, "scripts/run_real_pipeline.py"],
            cwd=dest, env=env, capture_output=True, text=True, timeout=600,
        )
        if proc.returncode != 0:
            return [f"pipeline re-run failed (exit {proc.returncode}):\n{proc.stderr[-2000:]}"]
        rerun = json.loads((dest / "reports" / "real_run" / "summary.json").read_text(encoding="utf-8"))
        for keys in MAE_PATHS:
            frozen_val = _get(frozen, keys)
            rerun_val = _get(rerun, keys)
            if abs(float(frozen_val) - float(rerun_val)) > 1e-9:
                problems.append(f"MAE mismatch {'.'.join(keys)}: frozen {frozen_val} vs re-run {rerun_val}")
        for key in ("posts", "news", "prices_rows"):
            if frozen.get(key) != rerun.get(key):
                problems.append(f"count mismatch {key}: frozen {frozen.get(key)} vs re-run {rerun.get(key)}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the frozen 2026-11-14 run package.")
    parser.add_argument("--reproduce", action="store_true", help="also re-run the pipeline from the frozen data")
    args = parser.parse_args()

    problems = verify_manifest()
    if problems:
        print("MANIFEST CHECK FAILED:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print(f"Manifest OK: {len(MANIFEST.read_text().splitlines())} files verified.")

    if args.reproduce:
        problems = reproduce()
        if problems:
            print("REPRODUCE CHECK FAILED:")
            for problem in problems:
                print(f"  - {problem}")
            return 1
        print("Reproduce OK: re-run MAEs match the frozen summary exactly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
