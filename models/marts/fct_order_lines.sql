-- Every item sold, in store or online. Online orders with no pickup store are deliveries, which ship from Pearl.
select
    pos_line_id as order_line_id,
    'in_store' as channel,
    transaction_id as order_id,
    store_id,
    ordered_at,
    order_date,
    sku,
    quantity,
    unit_price,
    line_total,
    is_refund,
    false as is_delivery
from {{ ref('stg_pos_lines') }}

union all

select
    online_line_id,
    'online',
    order_id,
    coalesce(store_id, 'pearl'),
    ordered_at,
    order_date,
    sku,
    quantity,
    unit_price,
    line_total,
    false,
    store_id is null
from {{ ref('stg_online_order_lines') }}
where order_status = 'paid'
