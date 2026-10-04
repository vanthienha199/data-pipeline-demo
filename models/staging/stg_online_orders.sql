-- One row per online order, as of its latest event. Test orders are excluded.
with latest as (
    select
        *,
        row_number() over (partition by order_id order by received_at desc) as recency
    from {{ ref('stg_order_events') }}
    where not is_test
)

select
    order_id,
    payload ->> 'store_pickup' as store_id,
    timezone('America/Los_Angeles', cast(payload ->> 'created_at' as timestamptz)) as ordered_at,
    cast(timezone('America/Los_Angeles', cast(payload ->> 'created_at' as timestamptz)) as date) as order_date,
    order_status,
    cast(payload ->> 'total_cents' as integer) / 100.0 as order_total,
    payload -> 'line_items' as line_items
from latest
where recency = 1
