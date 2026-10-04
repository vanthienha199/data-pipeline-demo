# Copper Kettle data pipeline (sample)

A small ELT pipeline for a made up chain of three coffee shops in Portland. Each morning a GitHub Actions run does five things:

1. Pulls real daily weather for each shop from the public Open-Meteo API.
2. Collects the shops' messy POS exports and the dump of online order webhooks.
3. Loads everything untouched into DuckDB.
4. Models and tests it with dbt.
5. Publishes a KPI page and the model docs to GitHub Pages.

The shop data is synthetic. The weather is real, and the sales were generated to react to it, so the marts tell a true story about a fake business.

Live site: https://vanthienha199.github.io/data-pipeline-demo/ (KPIs), with `lineage.html` and `docs/` beside it.

## What the raw data looks like, and what the models do about it

| Raw problem | Where | Handled in |
|---|---|---|
| Two POS export formats: comma vs semicolon, `10/03/2026` + `1:06 PM` vs ISO timestamps, `$4.15` vs `4.15` | `raw.pos_standard`, `raw.pos_alberta` | `stg_pos_lines` parses both into one shape |
| The same store written four ways: `Pearl`, `PEARL DISTRICT `, `pearl` | POS `Store` / `location` | Mapped to `pearl`, `alberta`, `division`, with an `accepted_values` test |
| Re-exported duplicate lines, about 1.5% | POS files | Deduped on transaction and line number. `pos_dedupe_removes_only_copies` proves nothing else is dropped |
| Refunds as negative quantities, blank tenders | POS | `is_refund` flag, tender normalized to `card`, `cash`, `apple_pay`, `unknown` |
| Webhooks delivered twice, cancellations arriving as later events, test orders | `raw.order_webhooks` | `stg_order_events` dedupes on event_id, and `stg_online_orders` keeps the latest status and drops tests |
| Amounts in cents, times in UTC, line items nested in JSON | webhooks | Converted to dollars and Pacific time, line items unnested |
| The forecast API returns null for days older than about 10 weeks | Open-Meteo | `extract_weather.py` fills those days from the archive API. A not-null test on the KPI view caught this the first time |

Lineage: four raw sources and two seeds feed five staging models, two dimensions and two facts, which end in `mart_daily_store_kpis`. That view has one row per shop per day with orders, revenue, average order, online share and cold drink share, next to that day's temperature and rain.

## Tests

The last build ran 52 nodes: 40 data tests plus the models and seeds, all passing. There are 4 source freshness checks.

- Generic tests: `unique`, `not_null`, `accepted_values`, `relationships`, plus a custom `unique_combination` for the store by day grain.
- Singular tests:
  - `revenue_reconciles`: the mart equals its order lines to the cent.
  - `pos_dedupe_removes_only_copies`
  - `no_orders_in_the_future`
- Freshness: warn after 36 hours and error after 60 hours for shop data, and a tighter window for weather.

## Run it locally

    python3.13 -m venv .venv && . .venv/bin/activate
    pip install -r requirements.txt
    ./run_pipeline.sh          # about 20 seconds, writes warehouse/ and site/
    open site/index.html

No cloud accounts or keys are needed. DuckDB is a single file in `warehouse/`, and the schedule lives in `.github/workflows/pipeline.yml`.

## Layout

    pipeline/extract_weather.py    E: Open-Meteo, with an archive fallback
    pipeline/generate_sources.py   stands in for the shops' daily exports and webhook dump
    pipeline/load_raw.py           L: raw files into the raw schema, untouched
    models/staging, models/marts   T: dbt models with tests and docs
    pipeline/lineage.py            lineage page drawn from dbt's manifest
    pipeline/report.py             KPI page with 30 day deltas and pipeline health
