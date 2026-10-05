"""Draws the model lineage from dbt's manifest.json as a layered SVG page at site/lineage.html."""
import json
from pathlib import Path

m = json.loads(Path("target/manifest.json").read_text())
nodes = {}
for uid, n in {**m["nodes"], **m["sources"]}.items():
    if n["resource_type"] not in ("model", "source", "seed"):
        continue
    name = n["name"] if n["resource_type"] != "source" else f"raw.{n['name']}"
    layer = {"source": 0, "seed": 1}.get(n["resource_type"]) if n["resource_type"] != "model" else (1 if n["name"].startswith("stg_") else 2 if n["name"].startswith(("dim_", "fct_")) else 3)
    nodes[uid] = {"name": name, "layer": layer, "kind": n["resource_type"], "deps": [d for d in n.get("depends_on", {}).get("nodes", [])]}
tests_on = {}
for uid, n in m["nodes"].items():
    if n["resource_type"] == "test":
        for d in n["depends_on"]["nodes"]:
            tests_on[d] = tests_on.get(d, 0) + 1

GRID = {
    "raw.pos_standard": (0, 2), "raw.pos_alberta": (0, 3), "raw.order_webhooks": (0, 4), "raw.weather_daily": (0, 5.2),
    "stg_pos_lines": (1, 2.5), "stg_order_events": (1, 4), "stg_online_orders": (2, 4), "stg_online_order_lines": (3, 4),
    "menu": (2, 0), "stores": (2, 1), "dim_products": (3, 0), "dim_stores": (3, 1),
    "fct_order_lines": (4, 3), "fct_orders": (5, 4), "stg_weather_daily": (5, 5.2), "mart_daily_store_kpis": (6, 2.5),
}
missing = [n["name"] for n in nodes.values() if n["name"] not in GRID]
if missing:
    raise SystemExit(f"add these models to GRID in pipeline/lineage.py: {missing}")
W, boxw, boxh, rowh = 1600, 196, 58, 76
colw = (W - 80 - boxw) / 6
H = int(5.2 * rowh + boxh + 120)
pos = {u: (40 + GRID[n["name"]][0] * colw, 84 + GRID[n["name"]][1] * rowh) for u, n in nodes.items()}
edges = []
for u, n in nodes.items():
    for dd in n["deps"]:
        if dd in pos:
            (x1, y1), (x2, y2) = pos[dd], pos[u]
            sx, sy, ex, ey = x1 + boxw, y1 + boxh / 2, x2, y2 + boxh / 2
            hot = n["name"].startswith("mart_")
            edges.append(f'<path d="M{sx},{sy} C{sx + 40},{sy} {ex - 40},{ey} {ex},{ey}" class="e{' hot' if hot else ''}"/>')
boxes = []
for u, (x, y) in pos.items():
    n = nodes[u]
    cls = "kpi" if n["name"].startswith("mart_") else n["kind"]
    t = tests_on.get(u, 0)
    sub = f"{t} test{'s' if t != 1 else ''}" if t else ("seed" if n["kind"] == "seed" else "source")
    boxes.append(f'<rect x="{x}" y="{y}" width="{boxw}" height="{boxh}" rx="10" class="b {cls}"/><text x="{x + 12}" y="{y + 24}" class="bt">{n["name"]}</text><text x="{x + 12}" y="{y + 44}" class="{"tb" if t else "tm"}">{sub}</text>')
labels = {0: "Raw sources", 1: "Staging", 2: "Seeds and dimensions", 4: "Facts", 6: "Daily board"}
heads = "".join(f'<text x="{40 + k * colw}" y="46" class="h">{v}</text>' for k, v in labels.items())
svg = f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">{heads}{"".join(edges)}{"".join(boxes)}</svg>'
css = """body{margin:0;background:#F1E9DC;font-family:"Work Sans",system-ui,sans-serif}svg{display:block;width:100%;height:auto}
.h{fill:#6D665B;font:600 14px "Work Sans",sans-serif}.e{fill:none;stroke:#C9BCA6;stroke-width:1.6}.e.hot{stroke:#B0603A;stroke-width:2}
.b{fill:#FBF7F0;stroke:#DDD2C0}.b.source{fill:#F6EFE3;stroke-dasharray:4 3}.b.seed{fill:#F6EFE3}.b.kpi{fill:#F7E6DB;stroke:#B0603A}
.bt{fill:#22201C;font:600 13.5px "Work Sans",sans-serif}.tm{fill:#8C8476;font:400 12px "Work Sans",sans-serif}.tb{fill:#5E7A4A;font:500 12px "Work Sans",sans-serif}"""
Path("site").mkdir(exist_ok=True)
Path("site/lineage.html").write_text(f'<!doctype html><html><head><meta charset="utf-8"><title>Lineage</title><link href="https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet"><style>{css}</style></head><body>{svg}</body></html>')
print(f"lineage: {len(nodes)} nodes, {len(edges)} edges")
