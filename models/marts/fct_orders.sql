select
    channel || ':' || order_id as order_key,
    channel,
    order_id,
    store_id,
    min(ordered_at) as ordered_at,
    min(order_date) as order_date,
    sum(case when quantity > 0 then quantity else 0 end) as items,
    sum(line_total) as revenue,
    bool_or(is_refund) as has_refund,
    bool_or(is_delivery) as is_delivery
from {{ ref('fct_order_lines') }}
group by all
