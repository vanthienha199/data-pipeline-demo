"""Builds site/index.html: the KPI view plus the pipeline's own health, from the warehouse and dbt artifacts."""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

SITE = Path("site")


def svg_chart(rows, w=1040, h=260):
    days = [r[0] for r in rows]
    rev = [r[1] for r in rows]
    temp = [r[2] for r in rows]
    pad_l, pad_b, pad_t = 56, 28, 12
    iw, ih = w - pad_l - 12, h - pad_b - pad_t
    rmax = max(rev) * 1.08
    tmin, tmax = min(temp) - 2, max(temp) + 2
    x = lambda i: pad_l + i * iw / max(1, len(rows) - 1)
    yr = lambda v: pad_t + ih - v / rmax * ih
    yt = lambda v: pad_t + ih - (v - tmin) / (tmax - tmin) * ih
    bars = "".join(f'<rect x="{x(i) - iw / len(rows) / 2 + 1:.1f}" y="{yt(t):.1f}" width="{max(1, iw / len(rows) - 2):.1f}" height="{pad_t + ih - yt(t):.1f}" class="t"/>' for i, t in enumerate(temp))
    line = " ".join(f"{x(i):.1f},{yr(v):.1f}" for i, v in enumerate(rev))
    grid = "".join(f'<line x1="{pad_l}" x2="{w - 12}" y1="{yr(v):.1f}" y2="{yr(v):.1f}" class="g"/><text x="{pad_l - 8}" y="{yr(v) + 4:.1f}" class="ax" text-anchor="end">${v / 1000:.0f}k</text>' for v in [rmax * f / 1.08 for f in (0.25, 0.5, 0.75, 1.0)])
    ticks = "".join(f'<text x="{x(i):.1f}" y="{h - 8}" class="ax" text-anchor="middle">{d:%b %-d}</text>' for i, d in enumerate(days) if i % 14 == 0)
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Daily revenue against max temperature">{grid}{bars}<polyline points="{line}" class="r"/>{ticks}</svg>'


def main():
    con = duckdb.connect("warehouse/copper_kettle.duckdb", read_only=True)
    q = lambda s: con.execute(s).fetchall()
    last_day = q("select max(order_date) from marts.mart_daily_store_kpis")[0][0]
    cur, prev = q(f"""
        select
          sum(revenue) filter (where order_date > date '{last_day}' - 30),
          sum(revenue) filter (where order_date <= date '{last_day}' - 30 and order_date > date '{last_day}' - 60),
          sum(orders) filter (where order_date > date '{last_day}' - 30),
          sum(orders) filter (where order_date <= date '{last_day}' - 30 and order_date > date '{last_day}' - 60),
          sum(online_orders) filter (where order_date > date '{last_day}' - 30),
          sum(online_orders) filter (where order_date <= date '{last_day}' - 30 and order_date > date '{last_day}' - 60)
        from marts.mart_daily_store_kpis""")[0], None
    rev, rev_p, orders, orders_p, onl, onl_p = cur
    aov, aov_p = rev / orders, rev_p / orders_p
    share, share_p = onl / orders, onl_p / orders_p
    delta = lambda a, b: (a - b) / b * 100
    kpis = [
        ("Revenue, last 30 days", f"${rev:,.2f}", delta(rev, rev_p)),
        ("Orders", f"{orders:,}", delta(orders, orders_p)),
        ("Average order", f"${aov:,.2f}", delta(aov, aov_p)),
        ("Online share", f"{share * 100:.1f}%", (share - share_p) * 100),
    ]
    daily = q("select order_date, sum(revenue), avg(temp_max_c) from marts.mart_daily_store_kpis group by 1 order by 1")
    stores = q(f"""select store_name, sum(revenue), sum(orders), sum(revenue) / sum(orders), avg(cold_drink_share)
                   from marts.mart_daily_store_kpis where order_date > date '{last_day}' - 30 group by 1 order by 2 desc""")
    weather = q("""select is_rainy, avg(online_share), avg(orders), count(*) from marts.mart_daily_store_kpis group by 1 order by 1""")
    corr = q("select corr(cold_drink_share, temp_max_c) from marts.mart_daily_store_kpis")[0][0]
    layers = q("""select 'raw', (select count(*) from raw.pos_standard) + (select count(*) from raw.pos_alberta) + (select count(*) from raw.order_webhooks)
                  union all select 'staging', (select count(*) from staging.stg_pos_lines) + (select count(*) from staging.stg_online_order_lines)
                  union all select 'marts', (select count(*) from marts.fct_order_lines)""")
    run = json.loads(Path("target/build_results.json").read_text())
    statuses = [r["status"] for r in run["results"]]
    tests = [r for r in run["results"] if r["unique_id"].startswith("test.")]
    fresh = json.loads(Path("target/sources.json").read_text()) if Path("target/sources.json").exists() else {"results": []}
    generated = datetime.now(timezone.utc).strftime("%b %-d, %Y %H:%M UTC")

    rows = "".join(f"<tr><td>{html.escape(s)}</td><td class=n>${r:,.2f}</td><td class=n>{o:,}</td><td class=n>${a:,.2f}</td><td class=n>{c * 100:.1f}%</td></tr>" for s, r, o, a, c in stores)
    cards = "".join(f'<div class="card"><p class="lab">{k}</p><p class="big">{v}</p><p class="{ "up" if d >= 0 else "down" }">{"▲" if d >= 0 else "▼"} {abs(d):.1f}{" pts" if k == "Online share" else "%"} vs prior 30 days</p></div>' for k, v, d in kpis)
    dry, wet = weather[0], weather[1]
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copper Kettle daily KPIs (sample pipeline)</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,700;12..96,800&family=IBM+Plex+Sans:wght@400;500;600&family=JetBrains+Mono:wght@500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#15171B;--s:#1E2126;--s2:#262A30;--line:#2E3238;--ink:#F3EFE7;--mut:#A7A39B;--acc:#F2994A;--ok:#7FD1A0;--bad:#F08A8A}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "IBM Plex Sans",system-ui,sans-serif}}
main{{max-width:1120px;margin:0 auto;padding:40px 24px 64px}}h1,h2{{font-family:"Bricolage Grotesque",Georgia,serif;letter-spacing:-.02em;margin:0}}
h1{{font-size:clamp(34px,5vw,52px);line-height:1.02}}h2{{font-size:22px;margin:40px 0 14px}}
.top{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;align-items:flex-end}}.tag{{font:600 11px "JetBrains Mono",monospace;letter-spacing:.08em;text-transform:uppercase;color:#F2C14A;background:rgba(242,193,74,.13);padding:5px 9px;border-radius:10px}}
.sub{{color:var(--mut);margin:8px 0 0}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:28px}}
.card{{background:var(--s);border:1px solid var(--line);border-radius:10px;padding:16px 18px}}.lab{{margin:0;font:500 11.5px "JetBrains Mono",monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--mut)}}
.big{{margin:6px 0 2px;font:600 28px "JetBrains Mono",monospace;font-variant-numeric:tabular-nums}}.up{{margin:0;color:var(--ok);font-size:13px}}.down{{margin:0;color:var(--bad);font-size:13px}}
.chart{{background:var(--s);border:1px solid var(--line);border-radius:10px;padding:16px;overflow-x:auto}}svg{{width:100%;min-width:640px;height:auto}}.r{{fill:none;stroke:var(--acc);stroke-width:2.2}}.t{{fill:#3A3E45}}.g{{stroke:var(--line)}}.ax{{fill:var(--mut);font:11px "JetBrains Mono",monospace}}
.legend{{display:flex;gap:18px;color:var(--mut);font-size:13px;margin:0 0 8px}}.legend i{{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}}
table{{width:100%;border-collapse:collapse;background:var(--s);border:1px solid var(--line);border-radius:10px;overflow:hidden}}th{{text-align:left;font:600 11px "JetBrains Mono",monospace;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);background:var(--s2);padding:10px 14px}}
td{{padding:11px 14px;border-top:1px solid var(--line)}}.n{{text-align:right;font-family:"JetBrains Mono",monospace;font-variant-numeric:tabular-nums}}th.n{{text-align:right}}
.two{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}.pill{{display:inline-block;font:600 12px "JetBrains Mono",monospace;padding:3px 8px;border-radius:8px;background:rgba(127,209,160,.12);color:var(--ok)}}
a{{color:var(--acc)}}footer{{margin-top:40px;color:var(--mut);font-size:13px}}
</style></head><body><main>
<div class="top"><div><h1>Copper Kettle, daily KPIs</h1><p class="sub">Three coffee shops in Portland. Data through {last_day:%b %-d, %Y}. Rebuilt {generated}.</p></div><span class="tag">Sample pipeline, fictional business</span></div>
<div class="grid">{cards}</div>
<h2>Daily revenue and the weather</h2>
<div class="chart"><p class="legend"><span><i style="background:#F2994A"></i>Daily revenue, all shops</span><span><i style="background:#3A3E45"></i>Max temperature</span></p>{svg_chart(daily)}</div>
<div class="two" style="margin-top:12px">
<div class="card"><p class="lab">Rainy days push orders online</p><p class="big">{wet[1] * 100:.1f}% <span style="font-size:15px;color:var(--mut)">vs {dry[1] * 100:.1f}% on dry days</span></p><p class="up" style="color:var(--mut)">{wet[3]} rainy and {dry[3]} dry shop days</p></div>
<div class="card"><p class="lab">Cold drinks track the temperature</p><p class="big">r = {corr:.2f}</p><p class="up" style="color:var(--mut)">daily cold drink share against max °C</p></div>
</div>
<h2>Shops, last 30 days</h2>
<table><thead><tr><th>Shop</th><th class=n>Revenue</th><th class=n>Orders</th><th class=n>Avg order</th><th class=n>Cold drinks</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Pipeline health</h2>
<div class="two">
<div class="card"><p class="lab">Last dbt build</p><p class="big">{statuses.count("pass") + statuses.count("success")}/{len(statuses)} <span class="pill">passed</span></p><p class="up" style="color:var(--mut)">{len(tests)} data tests, {len(statuses) - len(tests)} models and seeds</p></div>
<div class="card"><p class="lab">Source freshness</p><p class="big">{sum(1 for r in fresh['results'] if r.get('status') == 'pass')}/{len(fresh['results'])} <span class="pill">fresh</span></p><p class="up" style="color:var(--mut)">{layers[0][1]:,} raw records in, {layers[2][1]:,} clean order lines out</p></div>
</div>
<footer>Built by a scheduled GitHub Actions run: extract from Open-Meteo, load into DuckDB, transform and test with dbt. <a href="lineage.html">Lineage</a> and <a href="docs/">model docs</a>. All shop data is synthetic.</footer>
</main></body></html>"""
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(page)
    print(f"report written, data through {last_day}")


if __name__ == "__main__":
    main()
