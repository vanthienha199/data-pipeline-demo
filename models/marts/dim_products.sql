select sku, item_name, category, serve_temp, cast(list_price as decimal(10, 2)) as list_price
from {{ ref('menu') }}
