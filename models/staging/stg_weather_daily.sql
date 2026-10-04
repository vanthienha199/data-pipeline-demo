select
    store as store_id,
    cast(day as date) as weather_date,
    temp_max_c,
    temp_min_c,
    precip_mm,
    weather_code,
    precip_mm >= 2.0 as is_rainy
from {{ source('raw', 'weather_daily') }}
