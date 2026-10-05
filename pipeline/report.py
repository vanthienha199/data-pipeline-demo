"""Builds site/index.html: Copper Kettle's daily board, from the warehouse and dbt artifacts."""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

SITE = Path("site")
GREYS = {"pearl": "#8A8174", "alberta": "#A79D8E", "division": "#C2B8A8"}
COPPER = "#B0603A"


def chart(series, days, w=1040, h=280):
    pl, pr, pt, pb = 52, 16, 14, 30
    iw, ih = w - pl - pr, h - pt - pb
    vmax = max(max(v) for v in series.values()) * 1.1
    x = lambda i: pl + i * iw / max(1, len(days) - 1)
    y = lambda v: pt + ih - v / vmax * ih
    grid = "".join(f'<line x1="{pl}" x2="{w - pr}" y1="{y(v):.1f}" y2="{y(v):.1f}" class="g"/><text x="{pl - 8}" y="{y(v) + 4:.1f}" class="ax" text-anchor="end">{int(v)}</text>' for v in (vmax * f / 1.1 for f in (0.25, 0.5, 0.75, 1.0)))
    ticks = "".join(f'<text x="{x(i):.1f}" y="{h - 8}" class="ax" text-anchor="middle">{d:%b %-d}</text>' for i, d in enumerate(days) if i % 14 == 0)
    lines = "".join(f'<polyline data-store="{s}" class="ln" points="{" ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))}" style="--c:{GREYS[s]}"/>' for s, vals in series.items())
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="Cups sold per day by store">{grid}{lines}{ticks}</svg>'


def main():
    con = duckdb.connect("warehouse/copper_kettle.duckdb", read_only=True)
    q = lambda s, *a: con.execute(s, a).fetchall()
    last = q("select max(order_date) from marts.mart_daily_store_kpis")[0][0]
    board = q("""
        with d as (select * from marts.mart_daily_store_kpis)
        select t.store_id, s.neighborhood, t.cups, t.avg_order_value, t.revenue,
               (select avg(cups) from d p where p.store_id = t.store_id and p.order_date between ? - 7 and ? - 1) as wk,
               t.online_share, t.cold_drink_share
        from d t join marts.dim_stores s using (store_id)
        where t.order_date = ? order by t.cups desc""", last, last, last)
    top = board[0]
    top_delta = (top[2] - top[5]) / top[5] * 100
    headline = f"{top[1]} sold {top[2]:,} cups on {last:%A}, {'up' if top_delta >= 0 else 'down'} {abs(top_delta):.0f}% on its weekly average."
    days = [r[0] for r in q("select distinct order_date from marts.mart_daily_store_kpis order by 1")]
    series = {}
    for s in GREYS:
        m = dict(q("select order_date, cups from marts.mart_daily_store_kpis where store_id = ?", s))
        series[s] = [m.get(d, 0) for d in days]
    wet, dry = q("select avg(online_share) filter (where is_rainy), avg(online_share) filter (where not is_rainy) from marts.mart_daily_store_kpis")[0]
    corr = q("select corr(cold_drink_share, temp_max_c) from marts.mart_daily_store_kpis")[0][0]
    run = json.loads(Path("target/build_results.json").read_text())
    tests = [r for r in run["results"] if r["unique_id"].startswith("test.")]
    passed = sum(1 for r in run["results"] if r["status"] in ("pass", "success"))
    fresh = json.loads(Path("target/sources.json").read_text()) if Path("target/sources.json").exists() else {"results": []}
    fresh_ok = sum(1 for r in fresh["results"] if r.get("status") == "pass")
    raw_n = q("select (select count(*) from raw.pos_standard) + (select count(*) from raw.pos_alberta) + (select count(*) from raw.order_webhooks)")[0][0]
    lines_n = q("select count(*) from marts.fct_order_lines")[0][0]
    built = datetime.now(timezone.utc).strftime("%b %-d, %H:%M UTC")

    rows = "".join(f'''<tr data-store="{s}"><td class="rank">{i + 1}</td><td class="st">{html.escape(n)}</td>
<td class="n big">{c:,}</td><td class="n">${aov:.2f}</td><td class="n">${rev:,.2f}</td>
<td class="n {"up" if c >= wk else "down"}">{"+" if c >= wk else "−"}{abs((c - wk) / wk * 100):.0f}%</td></tr>''' for i, (s, n, c, aov, rev, wk, _o, _cd) in enumerate(board))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Copper Kettle, yesterday's board</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800&family=Work+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#F1E9DC;--s:#FBF7F0;--ink:#22201C;--mut:#6D665B;--line:#DDD2C0;--copper:{COPPER}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Work Sans",system-ui,sans-serif;font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}}
main{{max-width:1080px;margin:0 auto;padding:36px 24px 56px}}
.brand{{font:800 22px "Big Shoulders Display",sans-serif;letter-spacing:.01em}}
.date{{color:var(--mut);margin:2px 0 0}}
h1{{font:800 clamp(40px,6.4vw,72px)/1.0 "Big Shoulders Display",sans-serif;margin:26px 0 30px;max-width:900px;letter-spacing:.005em}}
.board{{background:var(--ink);color:#F4EEE4;border-radius:6px;padding:10px 26px 14px}}
.board table{{width:100%;border-collapse:collapse}}
.board th{{text-align:left;font-weight:500;color:#B8AE9E;font-size:14px;padding:14px 10px 10px;border-bottom:1px solid #4A443B}}
.board td{{padding:16px 10px;border-bottom:1px dashed #4A443B;font-size:18px}}
.board tr:last-child td{{border-bottom:0}}
.board tbody tr{{transition:background .15s ease-out;cursor:default}}
.board tbody tr:hover,.board tbody tr.on{{background:#2E2B26}}
.board tr.on .st,.board tbody tr:hover .st{{color:#E7A47F}}
.rank{{width:44px;color:#8F8678;font:800 26px "Big Shoulders Display",sans-serif}}
.st{{font:800 30px "Big Shoulders Display",sans-serif;letter-spacing:.01em;transition:color .15s ease-out}}
.n{{text-align:right;white-space:nowrap}}.big{{font:800 34px "Big Shoulders Display",sans-serif}}
th.n{{text-align:right}}.up{{color:#9CC59A}}.down{{color:#E7A47F}}
h2{{font:800 30px "Big Shoulders Display",sans-serif;margin:44px 0 6px}}
.sub{{color:var(--mut);margin:0 0 14px}}
.chart{{background:var(--s);border:1px solid var(--line);border-radius:6px;padding:16px 16px 8px;overflow-x:auto}}
svg{{width:100%;min-width:640px;height:auto;display:block}}.g{{stroke:var(--line)}}.ax{{fill:var(--mut);font:12px "Work Sans",sans-serif}}
.ln{{fill:none;stroke:var(--c);stroke-width:2;transition:stroke .15s ease-out,stroke-width .15s ease-out}}.ln.on{{stroke:var(--copper);stroke-width:3}}
.notes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-top:16px}}
.note{{background:var(--s);border:1px solid var(--line);border-radius:6px;padding:16px 18px}}
.note b{{display:block;font-size:17px;font-weight:600}}.note span{{color:var(--mut)}}
.health{{margin-top:44px;border-top:1px solid var(--line);padding-top:18px;color:var(--mut);display:flex;flex-wrap:wrap;gap:8px 28px}}
.health b{{color:var(--ink);font-weight:600}}
a{{color:var(--ink)}}footer{{margin-top:18px;color:var(--mut);font-size:14px}}
@media (max-width:640px){{.board{{padding:6px 12px}}.board th:nth-child(5),.board td:nth-child(5){{display:none}}.st{{font-size:24px}}.big{{font-size:28px}}}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}}}
</style></head><body><main>
<p class="brand">Copper Kettle</p><p class="date">Three coffee shops in Portland. Board for {last:%A, %B %-d}. Rebuilt {built}.</p>
<h1>{html.escape(headline)}</h1>
<div class="board"><table><thead><tr><th></th><th>Shop</th><th class="n">Cups</th><th class="n">Ticket</th><th class="n">Takings</th><th class="n">vs week</th></tr></thead><tbody>{rows}</tbody></table></div>
<h2>Cups a day, last 90 days</h2>
<p class="sub">Point at a shop on the board to light its line.</p>
<div class="chart">{chart(series, days)}</div>
<div class="notes">
<div class="note"><b>Rain pushes orders online</b><span>{wet * 100:.1f}% of orders came in online on rainy days, against {dry * 100:.1f}% on dry ones.</span></div>
<div class="note"><b>Heat sells cold drinks</b><span>The share of iced drinks tracks the day's high closely, a correlation of {corr:.2f}.</span></div>
</div>
<p class="health"><span><b>{passed} of {len(run["results"])}</b> dbt checks passed, including {len(tests)} data tests</span><span><b>{fresh_ok} of {len(fresh["results"])}</b> sources fresh</span><span><b>{raw_n:,}</b> raw records in, <b>{lines_n:,}</b> clean order lines out</span></p>
<footer><a href="lineage.html">How the data flows</a> and <a href="docs/">model docs</a>. Fictional business, invented data. Weather from the public Open-Meteo API.</footer>
</main>
<script>
const set = (s) => {{ document.querySelectorAll(".ln").forEach((l) => l.classList.toggle("on", l.dataset.store === s)); document.querySelectorAll("tbody tr").forEach((r) => r.classList.toggle("on", r.dataset.store === s)); }};
document.querySelectorAll("tbody tr").forEach((r) => {{ r.addEventListener("mouseenter", () => set(r.dataset.store)); r.addEventListener("focus", () => set(r.dataset.store)); r.tabIndex = 0; }});
document.querySelector("tbody").addEventListener("mouseleave", () => set("{top[0]}"));
set("{top[0]}");
</script></body></html>"""
    SITE.mkdir(exist_ok=True)
    (SITE / "index.html").write_text(page)
    print(f"report written, data through {last}")


if __name__ == "__main__":
    main()
