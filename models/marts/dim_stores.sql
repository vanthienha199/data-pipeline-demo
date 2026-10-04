select store_id, store_name, neighborhood, cast(opened_on as date) as opened_on, seats
from {{ ref('stores') }}
