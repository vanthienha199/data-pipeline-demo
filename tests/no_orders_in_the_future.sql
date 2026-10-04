select * from {{ ref('fct_orders') }} where order_date > current_date
