"""EL step: copy every raw file into the raw schema of the DuckDB warehouse, untouched, with load metadata."""
import time
from pathlib import Path

import duckdb

DB = Path("warehouse/copper_kettle.duckdb")


def main():
    DB.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("create schema if not exists raw")
    t0 = time.time()
    statements = {
        "raw.pos_standard": """
            select *, filename as _file, now() as _loaded_at
            from read_csv('data/raw/pos/pos_export_pearl_*.csv', all_varchar = true, filename = true, header = true)
            union all by name
            select *, filename as _file, now() as _loaded_at
            from read_csv('data/raw/pos/pos_export_division_*.csv', all_varchar = true, filename = true, header = true)""",
        "raw.pos_alberta": """
            select *, filename as _file, now() as _loaded_at
            from read_csv('data/raw/pos/pos_export_alberta_*.csv', delim = ';', all_varchar = true, filename = true, header = true)""",
        "raw.order_webhooks": """
            select event_id, type, received_at, to_json(payload) as payload, filename as _file, now() as _loaded_at
            from read_json('data/raw/webhooks/*.jsonl', format = 'newline_delimited', filename = true,
                           columns = {event_id: 'varchar', type: 'varchar', received_at: 'varchar', payload: 'json'})""",
        "raw.weather_daily": """
            with src as (select * from read_json('data/raw/weather/open_meteo_*.json', filename = true))
            select _store as store, _pulled_at as pulled_at,
                   unnest(daily.time) as day, unnest(daily.temperature_2m_max) as temp_max_c,
                   unnest(daily.temperature_2m_min) as temp_min_c, unnest(daily.precipitation_sum) as precip_mm,
                   unnest(daily.weather_code) as weather_code, filename as _file, now() as _loaded_at
            from src""",
    }
    for table, sql in statements.items():
        con.execute(f"create or replace table {table} as {sql}")
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"loaded {table:<22} {n:>9,} rows")
    print(f"raw load finished in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
