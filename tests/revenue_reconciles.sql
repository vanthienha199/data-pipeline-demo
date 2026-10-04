-- Revenue in the KPI mart must equal the order lines it was built from, to the cent.
with mart as (select sum(revenue) as r from {{ ref('mart_daily_store_kpis') }}),
lines as (select round(sum(line_total), 2) as r from {{ ref('fct_order_lines') }})
select mart.r as mart_revenue, lines.r as line_revenue
from mart, lines
where abs(mart.r - lines.r) > 0.05
