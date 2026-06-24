# Data Quality Assertions

For each check: **what it detects**, **what action to take when it fails**, and **how it would be monitored in production**.

## Primary key uniqueness (`customer_id`, `product_id`, `order_id`)
- **Detects:** duplicate primary keys in `customers_cleaned`, `products_cleaned`, `orders_cleaned` (and again in `dim_customers`, `dim_products`).
- **On failure:** fail the pipeline — duplicate keys break joins and inflate metrics.
- **Monitoring:** scheduled assertion run with alerting on failure; track duplicate count over time.

## Not-null keys and measures
- **Detects:** missing `customer_id` / `product_id` / `order_id`, and missing `quantity` / `price_per_unit` in `order_items_cleaned`.
- **On failure:** fail the pipeline — rows without keys cannot be joined or aggregated reliably.
- **Monitoring:** scheduled assertion run with alerting; dashboard the null rate per column.

## Positive quantity and price (`quantity > 0`, `price_per_unit > 0`)
- **Detects:** zero or negative quantities/prices in `order_items_cleaned`.
- **On failure:** quarantine the offending rows for review; they would distort revenue.
- **Monitoring:** scheduled assertion run; trend the count of invalid rows.

## Country present (`customers_cleaned.country` not null)
- **Detects:** customers with a missing/blank country (e.g. `C019`).
- **On failure:** alert and investigate with the business; do not block — handling is an open question.
- **Monitoring:** scheduled assertion run; track the count of missing-country customers.

## Country is ISO (`customers_country_is_iso.sqlx`)
- **Detects:** non-null country values that are not a valid ISO 3166-1 country name.
- **On failure:** quarantine and standardize the value (map to canonical ISO name).
- **Monitoring:** scheduled assertion run; alert on any non-ISO value appearing.
