-- The KPI view: one row per shop per day, with the weather that day.
with orders as (
    select
        store_id,
        order_date,
        count(*) as orders,
        count(*) filter (where channel = 'online') as online_orders,
        sum(revenue) as revenue,
        sum(revenue) filter (where channel = 'online') as online_revenue,
        count(*) filter (where has_refund) as refunds
    from {{ ref('fct_orders') }}
    group by all
),

drinks as (
    select
        l.store_id,
        l.order_date,
        sum(l.quantity) filter (where p.serve_temp = 'cold') as cold_drinks,
        sum(l.quantity) filter (where p.serve_temp in ('hot', 'cold')) as drinks
    from {{ ref('fct_order_lines') }} l
    join {{ ref('dim_products') }} p using (sku)
    where l.quantity > 0
    group by all
)

select
    o.order_date,
    o.store_id,
    s.store_name,
    o.orders,
    o.online_orders,
    round(o.revenue, 2) as revenue,
    round(o.revenue / o.orders, 2) as avg_order_value,
    round(o.online_orders / o.orders, 4) as online_share,
    round(d.cold_drinks / nullif(d.drinks, 0), 4) as cold_drink_share,
    o.refunds,
    w.temp_max_c,
    w.precip_mm,
    w.is_rainy
from orders o
join {{ ref('dim_stores') }} s using (store_id)
left join drinks d using (store_id, order_date)
left join {{ ref('stg_weather_daily') }} w on w.store_id = o.store_id and w.weather_date = o.order_date
