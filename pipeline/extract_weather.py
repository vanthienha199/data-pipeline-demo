import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

STORES = {"pearl": (45.5276, -122.6847), "alberta": (45.5590, -122.6450), "division": (45.5049, -122.6250)}
OUT = Path("data/raw/weather")
DAYS = 90


def fetch(lat, lon, start, end, url="https://api.open-meteo.com/v1/forecast"):
    params = {
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,weather_code",
        "timezone": "America/Los_Angeles",
    }
    for attempt in range(4):
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(2 ** attempt)
    r.raise_for_status()


def main():
    end = date.today()
    start = end - timedelta(days=DAYS - 1)
    OUT.mkdir(parents=True, exist_ok=True)
    pulled_at = datetime.now(timezone.utc).isoformat()
    for store, (lat, lon) in STORES.items():
        payload = fetch(lat, lon, start, end)
        daily = payload["daily"]
        missing = [i for i, v in enumerate(daily["temperature_2m_max"]) if v is None]
        if missing:
            a, b = date.fromisoformat(daily["time"][missing[0]]), date.fromisoformat(daily["time"][missing[-1]])
            archive = fetch(lat, lon, a, b, url="https://archive-api.open-meteo.com/v1/archive")["daily"]
            by_day = {d: i for i, d in enumerate(archive["time"])}
            for i in missing:
                j = by_day.get(daily["time"][i])
                if j is not None:
                    for k in ("temperature_2m_max", "temperature_2m_min", "precipitation_sum", "weather_code"):
                        daily[k][i] = archive[k][j]
            print(f"weather {store}: filled {len(missing)} older days from the archive API")
        payload["_store"] = store
        payload["_pulled_at"] = pulled_at
        (OUT / f"open_meteo_{store}.json").write_text(json.dumps(payload))
        print(f"weather {store}: {len(payload['daily']['time'])} days {start} to {end}")


if __name__ == "__main__":
    sys.exit(main())
