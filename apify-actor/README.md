# Apify Actor — cwt-public-finance-sources

Custom Actor that collects the assignment's 4 sources × 10 tickers from
public pages only (LIHKG, Moomoo Community, Naver Finance, Daum Finance),
10-day lookback, max 100 posts per source × asset, 2 s politeness delay.
No login, no paid proxy, no Store Actor.

## Files

- `main.py` — the Actor. `fetch_all()` is plain Python (no Apify SDK
  needed for the fetch logic); the SDK wrapper only reads the input and
  pushes rows to the dataset.
- `.actor/actor.json` — Actor metadata + input schema + dataset schema.
- `Dockerfile`, `requirements.txt` — `apify/actor-python:3.12` base.

## Create it in Shiv's Apify account (Shiv's account only)

```bash
cd apify-actor
npm install -g apify-cli        # once
apify login                     # Shiv's Apify account (Free plan)
apify push                      # creates the Actor, prints its ID
```

Then record the ID so the run script can use it:

```bash
echo '{"actor_id": "<the Actor ID from apify push>"}' > ../config/apify_actor.json
```

(Or pass `--actor-id` directly to the run script.)

## Run it (Shiv's token only)

```bash
export APIFY_API_TOKEN='<Shiv's token from console.apify.com/account/integrations>'
python scripts/run_apify_collection.py --dry-run        # allowance check only
python scripts/run_apify_collection.py --confirm-free-balance
```

The script checks the read-only usage/limits endpoints first, starts one
run with `config/apify_input.json`, waits, downloads the dataset and the
run log, and writes `data/apify/<run_id>/` (run.json, items.json, log.txt)
plus `data/normalized/apify_posts.csv`. It prints the Actor ID and run ID
— those are what goes in the submission email.

## Cost guard

- Free plan: $5/month platform-usage credits. The Actor is plain HTTP
  (no browser, no proxy), so one run of ~40 source × asset fetches is
  small compute, but **check the remaining balance in the dashboard
  before running** — the run script refuses without
  `--confirm-free-balance`.
- If the allowance genuinely cannot cover the run, do not substitute
  silently: tell Gilad (see `SUBMISSION_EMAIL.md`).

## Local test (no account needed)

```bash
python main.py --local-test --max-posts 3
```

Fetches the real public endpoints from this machine and prints per-source
counts. Last run 2026-11-14 (~8 min, mostly politeness delays): **691 rows
— 3 LIHKG, 23 Moomoo, 500 Naver, 165 Daum** (Naver/Daum below the local
collectors' counts because the Actor's config caps pages at 3 per
source × asset, vs 5 for the local Naver collector). The counts match the
local collectors' per-source pattern; LIHKG stays thin for the documented
reasons.
