#!/usr/bin/env bash
set -euo pipefail
export DBT_PROFILES_DIR=.
PY=${PYTHON:-python}
mkdir -p site/docs
{
  echo "== extract =="; $PY pipeline/extract_weather.py
  echo "== generate synthetic shop exports =="; $PY pipeline/generate_sources.py
  echo "== load raw =="; $PY pipeline/load_raw.py
  echo "== transform and test =="; dbt build --no-use-colors; cp target/run_results.json target/build_results.json
  echo "== freshness =="; dbt source freshness --no-use-colors
  echo "== docs =="; dbt docs generate --static --no-use-colors
} 2>&1 | tee site/run_log.txt
cp target/static_index.html site/docs/index.html
$PY pipeline/lineage.py
$PY pipeline/report.py
