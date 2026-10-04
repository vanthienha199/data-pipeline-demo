"""Writes the two synthetic sources a small coffee chain would actually have:
daily POS CSV exports per store and a dump of online order webhooks.
Sales follow the real weather pulled from Open-Meteo, so the marts tell a true story about the fake shop."""
import csv
import json
import random
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

RAW = Path("data/raw")
MENU = [
    ("ESP-DBL", "Double espresso", 3.75, "hot"), ("LAT-12", "Latte 12oz", 5.25, "hot"), ("LAT-16", "Latte 16oz", 5.95, "hot"),
    ("CAP-12", "Cappuccino", 5.10, "hot"), ("DRP-12", "Drip coffee", 3.40, "hot"), ("MOC-16", "Mocha 16oz", 6.25, "hot"),
    ("ICL-16", "Iced latte 16oz", 6.10, "cold"), ("CBR-16", "Cold brew 16oz", 5.45, "cold"), ("ICT-16", "Iced tea", 4.15, "cold"),
    ("CRS-01", "Butter croissant", 4.25, "food"), ("SCN-01", "Marionberry scone", 4.50, "food"), ("BRK-01", "Breakfast burrito", 9.75, "food"),
    ("BEN-12", "Whole bean 12oz bag", 17.50, "retail"),
]
STORE_LABELS = {"pearl": ["Pearl", "PEARL DISTRICT ", "pearl"], "alberta": ["Alberta St", "alberta"], "division": ["Division", "DIVISION ST"]}
BASE = {"pearl": 310, "alberta": 240, "division": 205}


def weather():
    w = {}
    for f in sorted((RAW / "weather").glob("open_meteo_*.json")):
        d = json.loads(f.read_text())
        store = d["_store"]
        for i, day in enumerate(d["daily"]["time"]):
            w[(store, day)] = (d["daily"]["temperature_2m_max"][i] or 18.0, d["daily"]["precipitation_sum"][i] or 0.0)
    return w


def day_txns(store, day, tmax, rain, rng):
    n = int(BASE[store] * (1.12 if day.weekday() >= 5 else 1.0) * (0.78 if rain > 2 else 1.0) * rng.uniform(0.9, 1.1))
    cold_share = min(0.75, max(0.08, (tmax - 12) / 25))
    rows = []
    for _ in range(n):
        minute = int(rng.triangular(6.5 * 60, 18 * 60, 8.3 * 60))
        ts = datetime.combine(day, time(minute // 60, minute % 60, rng.randint(0, 59)))
        items = []
        for _ in range(rng.choices([1, 2, 3], [0.62, 0.3, 0.08])[0]):
            kind = rng.choices(["drink", "food", "retail"], [0.78, 0.2, 0.02])[0]
            if kind == "drink":
                temp = "cold" if rng.random() < cold_share else "hot"
                pool = [m for m in MENU if m[3] == temp]
            else:
                pool = [m for m in MENU if m[3] == kind]
            items.append(rng.choice(pool))
        rows.append((ts, items))
    return rows


def write_pos(store, day, txns, rng):
    out = RAW / "pos"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"pos_export_{store}_{day:%Y%m%d}.csv"
    seq = 0
    if store == "alberta":
        with path.open("w", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["transaction_id", "line_no", "timestamp", "sku", "item", "qty", "unit_price", "line_total", "tender", "location"])
            for ts, items in txns:
                seq += 1
                tid = f"AB-{day:%y%m%d}-{seq:04d}"
                tender = rng.choice(["card", "card", "card", "apple_pay", "cash", ""])
                for ln, (sku, name, price, _) in enumerate(items, 1):
                    qty = -1 if rng.random() < 0.006 else 1
                    row = [tid, ln, ts.strftime("%Y-%m-%dT%H:%M:%S"), sku, name, qty, f"{price:.2f}", f"{price * qty:.2f}", tender, rng.choice(STORE_LABELS[store])]
                    w.writerow(row)
                    if rng.random() < 0.015:
                        w.writerow(row)
    else:
        with path.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Txn ID", "Line #", "Date", "Time", "SKU", "Item", "Qty", "Unit Price", "Total", "Payment", "Store"])
            for ts, items in txns:
                seq += 1
                tid = f"{store[:2].upper()}{day:%m%d}{seq:05d}"
                tender = rng.choice(["Visa", "Mastercard", "AMEX", "Cash", "Apple Pay", None])
                for ln, (sku, name, price, _) in enumerate(items, 1):
                    qty = -1 if rng.random() < 0.006 else 1
                    row = [tid, ln, ts.strftime("%m/%d/%Y"), ts.strftime("%-I:%M %p"), sku, name if rng.random() > 0.01 else name.upper(), qty, f"${price:.2f}", f"${price * qty:.2f}", tender or "", rng.choice(STORE_LABELS[store])]
                    w.writerow(row)
                    if rng.random() < 0.015:
                        w.writerow(row)


def write_webhooks(day, w, rng):
    out = RAW / "webhooks"
    out.mkdir(parents=True, exist_ok=True)
    events = []
    for store in BASE:
        tmax, rain = w.get((store, day.isoformat()), (18.0, 0.0))
        n = int(BASE[store] * 0.11 * (1.45 if rain > 2 else 1.0) * rng.uniform(0.85, 1.15))
        for i in range(n):
            created = datetime.combine(day, time(rng.randint(7, 17), rng.randint(0, 59)), tzinfo=timezone(timedelta(hours=-7))).astimezone(timezone.utc)
            oid = f"ORD-{day:%y%m%d}-{store[:1].upper()}{i:03d}"
            lines = [{"sku": m[0], "name": m[1], "quantity": rng.choice([1, 1, 1, 2]), "price_cents": round(m[2] * 100)} for m in rng.sample(MENU, rng.choice([1, 2, 2, 3]))]
            total = sum(l["quantity"] * l["price_cents"] for l in lines)
            payload = {"order_id": oid, "created_at": created.isoformat().replace("+00:00", "Z"), "store_pickup": store if rng.random() > 0.02 else None,
                       "customer": {"email": f"guest{rng.randint(1000, 99999)}@example.com"}, "line_items": lines, "total_cents": total, "test": rng.random() < 0.01, "status": "paid"}
            ev = {"event_id": f"evt_{rng.getrandbits(48):012x}", "type": "order.created", "received_at": (created + timedelta(seconds=rng.randint(1, 40))).isoformat().replace("+00:00", "Z"), "payload": payload}
            events.append(ev)
            if rng.random() < 0.03:
                events.append(dict(ev))
            if rng.random() < 0.04:
                upd = json.loads(json.dumps(ev))
                upd["event_id"] = f"evt_{rng.getrandbits(48):012x}"
                upd["type"] = "order.cancelled"
                upd["payload"]["status"] = "cancelled"
                upd["received_at"] = (created + timedelta(minutes=rng.randint(3, 50))).isoformat().replace("+00:00", "Z")
                events.append(upd)
    rng.shuffle(events)
    (out / f"webhooks_{day:%Y%m%d}.jsonl").write_text("\n".join(json.dumps(e) for e in events) + "\n")


def main():
    w = weather()
    days = sorted({d for (_, d) in w})
    today = date.today()
    for d in days:
        day = date.fromisoformat(d)
        if day >= today:
            continue
        rng = random.Random(f"copper-kettle-{d}")
        for store in BASE:
            tmax, rain = w[(store, d)]
            write_pos(store, day, day_txns(store, day, tmax, rain, rng), rng)
        write_webhooks(day, w, rng)
    print(f"sources written for {len(days)} days")


if __name__ == "__main__":
    main()
