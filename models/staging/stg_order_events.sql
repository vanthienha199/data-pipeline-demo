-- Webhook events with retries removed. The same event_id can arrive more than once.
with ranked as (
    select
        *,
        row_number() over (partition by event_id order by _loaded_at) as delivery_number
    from {{ source('raw', 'order_webhooks') }}
)

select
    event_id,
    type as event_type,
    cast(received_at as timestamptz) as received_at,
    payload ->> 'order_id' as order_id,
    payload ->> 'status' as order_status,
    cast(payload ->> 'test' as boolean) as is_test,
    payload
from ranked
where delivery_number = 1
