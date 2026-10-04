-- Dedupe must drop re-exported copies and nothing else: staged lines equal distinct raw lines.
with raw_distinct as (
    select count(*) as n from (
        select distinct "Txn ID", "Line #", "Date", "Time", "SKU", "Qty", "Total" from {{ source('raw', 'pos_standard') }}
        union all
        select distinct transaction_id, line_no, "timestamp", sku, qty, line_total, null from {{ source('raw', 'pos_alberta') }}
    )
),
staged as (select count(*) as n from {{ ref('stg_pos_lines') }})
select raw_distinct.n as raw_lines, staged.n as staged_lines
from raw_distinct, staged
where raw_distinct.n != staged.n
