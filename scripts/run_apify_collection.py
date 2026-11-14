#!/usr/bin/env python3
"""Run the custom Apify Actor and keep the run evidence (Fix 1).

    python scripts/run_apify_collection.py --actor-id <actor-id> --dry-run
    python scripts/run_apify_collection.py --actor-id <actor-id> \
        --confirm-free-balance

The script:
  1. Reads APIFY_API_TOKEN from the environment (never from a file, never
     printed). Refuses without it.
  2. Calls the read-only usage/limits endpoints and prints the account's
     remaining Free-plan platform-usage credits. It refuses to start a run
     unless --confirm-free-balance is passed (confirm in the Apify
     dashboard that free credits remain and that no paid proxy / paid
     Actor is involved).
  3. Starts a run of the Actor with config/apify_input.json, waits for it
     to finish, downloads the dataset items, and writes:
       data/apify/<run_id>/run.json        (Actor ID, run ID, status, stats)
       data/apify/<run_id>/items.json      (raw dataset items)
       data/apify/<run_id>/log.txt         (run log)
       data/normalized/apify_posts.csv     (normalised rows, pipeline format)
  4. Prints the Actor ID, run ID and row counts — the IDs Gilad needs.

The Actor itself lives in apify-actor/ (see its README for how to create it
in Shiv's Apify account). This script never creates an Actor and never
spends anything except the one run it starts after the confirmation gate.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "config" / "apify_input.json"
API = "https://api.apify.com/v2"
ACTOR_ID_FILE = ROOT / "config" / "apify_actor.json"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def check_allowance(token: str) -> dict:
    """Read-only usage/limits check. Returns the raw responses."""
    usage = requests.get(f"{API}/users/me/usage/monthly", headers=_headers(token), timeout=30)
    usage.raise_for_status()
    limits = requests.get(f"{API}/users/me/limits", headers=_headers(token), timeout=30)
    limits.raise_for_status()
    return {"usage_monthly": usage.json(), "limits": limits.json()}


def _print_allowance(data: dict) -> None:
    usage = data["usage_monthly"].get("data", data["usage_monthly"])
    print("Apify monthly usage (read-only):")
    print(json.dumps(usage, indent=2)[:1500])
    print("Apify limits (read-only):")
    print(json.dumps(data["limits"].get("data", data["limits"]), indent=2)[:1500])


def start_run(token: str, actor_id: str, actor_input: dict) -> dict:
    resp = requests.post(
        f"{API}/acts/{actor_id}/runs",
        headers=_headers(token), json=actor_input, timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def wait_for_run(token: str, run_id: str, timeout_s: int = 1800) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(f"{API}/actor-runs/{run_id}", headers=_headers(token), timeout=30)
        resp.raise_for_status()
        run = resp.json()["data"]
        if run["status"] in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
            return run
        time.sleep(15)
    raise TimeoutError(f"run {run_id} did not finish within {timeout_s}s")


def fetch_dataset(token: str, dataset_id: str) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        resp = requests.get(
            f"{API}/datasets/{dataset_id}/items",
            headers=_headers(token),
            params={"limit": 1000, "offset": offset, "clean": "true"},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        items.extend(batch)
        offset += len(batch)
    return items


def fetch_log(token: str, run_id: str) -> str:
    resp = requests.get(f"{API}/actor-runs/{run_id}/log", headers=_headers(token), timeout=60)
    return resp.text if resp.status_code == 200 else f"(log unavailable: HTTP {resp.status_code})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the CWT Apify Actor and keep the evidence.")
    parser.add_argument("--actor-id", default=None,
                        help="Actor ID (default: config/apify_actor.json, else required)")
    parser.add_argument("--confirm-free-balance", action="store_true",
                        help="confirm free credits remain and no paid proxy/Actor is used")
    parser.add_argument("--dry-run", action="store_true",
                        help="check the token + allowance only; start no run")
    args = parser.parse_args()

    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        print("APIFY_API_TOKEN is not set. This must be Shiv's Apify API token "
              "(his Apify account, Free plan) — create it at "
              "https://console.apify.com/account/integrations and export it; "
              "never paste it into a file or chat.", file=sys.stderr)
        return 2

    actor_id = args.actor_id
    if not actor_id and ACTOR_ID_FILE.exists():
        actor_id = json.loads(ACTOR_ID_FILE.read_text(encoding="utf-8")).get("actor_id")
    if not actor_id and not args.dry_run:
        print("No Actor ID. Pass --actor-id, or write config/apify_actor.json "
              "after creating the Actor (see apify-actor/README.md).", file=sys.stderr)
        return 2

    print("Checking Apify allowance (read-only)...")
    allowance = check_allowance(token)
    _print_allowance(allowance)
    if args.dry_run:
        print("Dry run only: no Actor run started.")
        return 0
    if not args.confirm_free_balance:
        print("Refused: confirm in the Apify dashboard that free platform-usage "
              "credits remain and that no paid proxy is enabled, then re-run with "
              "--confirm-free-balance.", file=sys.stderr)
        return 2

    actor_input = json.loads(INPUT.read_text(encoding="utf-8"))
    actor_input.pop("template_only", None)
    actor_input.pop("warning", None)
    print(f"Starting run of Actor {actor_id} ...")
    run = start_run(token, actor_id, actor_input)
    run_id = run["id"]
    print(f"Run started: {run_id} (https://console.apify.com/actors/runs/{run_id})")
    run = wait_for_run(token, run_id)
    print(f"Run finished with status: {run['status']}")

    out_dir = ROOT / "data" / "apify" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "run.json").write_text(json.dumps({
        "actor_id": actor_id, "run_id": run_id, "status": run["status"],
        "started_at": run.get("startedAt"), "finished_at": run.get("finishedAt"),
        "stats": run.get("stats"), "usage": run.get("usage"),
        "default_dataset_id": run.get("defaultDatasetId"),
    }, indent=2), encoding="utf-8")
    (out_dir / "log.txt").write_text(fetch_log(token, run_id), encoding="utf-8")

    if run["status"] != "SUCCEEDED":
        print(f"Run did not succeed ({run['status']}). See {out_dir}/log.txt", file=sys.stderr)
        return 1
    items = fetch_dataset(token, run["defaultDatasetId"])
    (out_dir / "items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    df = pd.DataFrame(items)
    cols = ["ticker", "source", "timestamp_utc", "text", "likes", "reposts",
            "views", "author_followers", "post_id", "url"]
    for col in cols:
        if col not in df.columns:
            df[col] = None
    df[cols].to_csv(ROOT / "data" / "normalized" / "apify_posts.csv", index=False)
    print(f"Actor ID: {actor_id}")
    print(f"Run ID: {run_id}")
    print(f"Dataset items: {len(items)} -> data/normalized/apify_posts.csv")
    print(f"Evidence in {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
