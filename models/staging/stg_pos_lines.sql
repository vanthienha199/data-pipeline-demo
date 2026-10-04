-- One row per POS line, both export formats in one shape. Re-exported copies of a line (same transaction and line number) are dropped.
with standard as (
    select
        "Txn ID" as transaction_id,
        try_cast("Line #" as integer) as line_number,
        strptime("Date" || ' ' || "Time", '%m/%d/%Y %I:%M %p') as ordered_at,
        upper(trim("SKU")) as sku,
        try_cast("Qty" as integer) as quantity,
        try_cast(replace("Unit Price", '$', '') as decimal(10, 2)) as unit_price,
        try_cast(replace("Total", '$', '') as decimal(10, 2)) as line_total,
        nullif(trim("Payment"), '') as tender_raw,
        "Store" as store_raw,
        _file,
        _loaded_at
    from {{ source('raw', 'pos_standard') }}
),

alberta as (
    select
        transaction_id,
        try_cast(line_no as integer) as line_number,
        cast("timestamp" as timestamp) as ordered_at,
        upper(trim(sku)) as sku,
        try_cast(qty as integer) as quantity,
        try_cast(unit_price as decimal(10, 2)) as unit_price,
        try_cast(line_total as decimal(10, 2)) as line_total,
        nullif(trim(tender), '') as tender_raw,
        location as store_raw,
        _file,
        _loaded_at
    from {{ source('raw', 'pos_alberta') }}
),

unioned as (
    select * from standard
    union all
    select * from alberta
),

deduped as (
    select
        *,
        row_number() over (partition by transaction_id, line_number order by _file) as copy_number
    from unioned
)

select
    md5(transaction_id || '|' || cast(line_number as varchar)) as pos_line_id,
    transaction_id,
    line_number,
    case
        when lower(store_raw) like '%pearl%' then 'pearl'
        when lower(store_raw) like '%alberta%' then 'alberta'
        when lower(store_raw) like '%division%' then 'division'
    end as store_id,
    ordered_at,
    cast(ordered_at as date) as order_date,
    sku,
    quantity,
    unit_price,
    line_total,
    case
        when tender_raw is null then 'unknown'
        when lower(tender_raw) = 'cash' then 'cash'
        when lower(replace(tender_raw, ' ', '_')) = 'apple_pay' then 'apple_pay'
        else 'card'
    end as tender,
    quantity < 0 as is_refund
from deduped
where copy_number = 1
