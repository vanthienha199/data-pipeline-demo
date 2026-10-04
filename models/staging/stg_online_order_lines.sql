with items as (
    select
        order_id,
        store_id,
        ordered_at,
        order_date,
        order_status,
        unnest(from_json(line_items, '[{"sku":"VARCHAR","quantity":"INTEGER","price_cents":"INTEGER"}]'), recursive := true)
    from {{ ref('stg_online_orders') }}
)

select
    md5(order_id || '|' || sku) as online_line_id,
    order_id,
    store_id,
    ordered_at,
    order_date,
    order_status,
    upper(sku) as sku,
    quantity,
    price_cents / 100.0 as unit_price,
    quantity * price_cents / 100.0 as line_total
from items
