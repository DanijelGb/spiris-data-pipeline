# Data Quality Assertions

For each check: **what it detects**, **what action to take when it fails**, and **how it would be monitored in production**.

Checks fall into three layers:
- **Source checks** (tagged `source`) assert the *raw* tables to surface rows the staging clean step would silently drop, so incoming data loss is observable instead of invisible.
- **Within-table checks** assert invariants on a single cleaned/modeled table (keys not null/unique, measures in range).
- **Cross-table checks** assert relationships between tables (foreign keys resolve).

The files are organized into subfolders by layer (folder location does not affect compilation; `${ref}` still resolves):
- `source/` — raw-table checks (`raw_*`).
- `staging/` — single-table checks on the cleaned tables.
- `cross_table/` — referential-integrity checks between tables.

PK invariants are asserted once, at staging (`customers_cleaned`, `products_cleaned`, `orders_cleaned`), where they are established. The dimensions (`dim_customers`, `dim_products`) are pass-throughs and intentionally do **not** re-assert them.

---

## Source checks (tagged `source`)

### Source key quality (`raw_orders_key_quality`, `raw_customers_key_quality`, `raw_products_key_quality`, `raw_order_items_key_quality`)
- **Detects:** in the raw tables, the rows the staging step would silently remove — null primary/foreign keys (dropped by the `WHERE` filter) and duplicate primary keys (collapsed by the dedup). `order_items` has no single PK, so only its null foreign keys are checked.
- **On failure:** investigate the upstream source/ingestion; a non-empty result means real rows are being discarded during cleaning. Decide whether to fix at source, recover, or accept the drop.
- **Monitoring:** scheduled assertion run; trend the count of dropped rows per table. Tagged `source` so it can be run/monitored independently of the blocking build.

### Non-positive measures (`raw_order_items_non_positive_measures`)
- **Detects:** raw `order_items` rows the clean step discards because `quantity <= 0` or `price_per_unit <= 0` (the staging filter keeps only `> 0`; zero is dropped too). Each row is returned with an `issue` label.
- **On failure:** investigate the source — non-positive quantities/prices usually indicate a data-entry or upstream error; decide whether to correct or accept the drop.
- **Monitoring:** scheduled assertion run; trend the count of discarded rows. Tagged `source`.

---

## Within-table checks

### Primary key uniqueness (`customer_id`, `product_id`, `order_id`)
- **Detects:** duplicate primary keys in `customers_cleaned`, `products_cleaned`, `orders_cleaned`.
- **On failure:** fail the pipeline — duplicate keys break joins and inflate metrics.
- **Monitoring:** scheduled assertion run with alerting on failure; track duplicate count over time.

### Not-null keys and measures
- **Detects:** missing `customer_id` / `product_id` / `order_id`, and missing `quantity` / `price_per_unit` in `order_items_cleaned`.
- **On failure:** fail the pipeline — rows without keys cannot be joined or aggregated reliably.
- **Monitoring:** scheduled assertion run with alerting; dashboard the null rate per column.

### Positive quantity and price (`quantity > 0`, `price_per_unit > 0`)
- **Detects:** zero or negative quantities/prices in `order_items_cleaned`. This is a **redundant backstop**: the staging step already drops non-positive rows in its `WHERE` filter, so on clean data this check passes by construction. It guards against a future regression in that filter; the primary detection of discarded rows lives in the source check `raw_order_items_non_positive_measures`.
- **On failure:** the staging filter has regressed (it should have removed these rows) — fix the cleaning logic. Non-positive measures would otherwise distort revenue.
- **Monitoring:** scheduled assertion run; a non-zero count signals a staging-filter regression rather than a new source issue.

### Order status present (`orders_status_present.sqlx`)
- **Detects:** orders in `orders_cleaned` with a NULL `order_status` (blank in source, or a value not in completed/cancelled/refunded that the clean step mapped to NULL).
- **On failure:** investigate the source value; an unrecognized status may signal a new valid state to add, or a data error.
- **Monitoring:** scheduled assertion run; track the count and trend of missing/unrecognized statuses.

### Order timestamp present (`orders_timestamp_present.sqlx`)
- **Detects:** orders in `orders_cleaned` with a NULL `order_timestamp` (missing or unparseable in source; `SAFE_CAST` returned NULL).
- **On failure:** investigate the source value; an order with no timestamp cannot be placed on the time axis of the marts (e.g. `daily_sales`).
- **Monitoring:** scheduled assertion run; trend the count of orders missing a timestamp.

### Country present (`customers_country_present.sqlx`)
- **Detects:** customers with a missing/blank country (e.g. `C019`).
- **On failure:** alert and investigate with the business; handling is an open question.
- **Monitoring:** scheduled assertion run; track the count of missing-country customers.

### Signup date present (`customers_signup_date_present.sqlx`)
- **Detects:** customers in `customers_cleaned` with a NULL `signup_date` (missing or unparseable in source; `SAFE_CAST` returned NULL).
- **On failure:** investigate the source value; a missing signup date weakens cohort/tenure analysis.
- **Monitoring:** scheduled assertion run; trend the count of customers missing a signup date.

### Country is ISO (`customers_country_is_iso.sqlx`)
- **Detects:** non-null country values that are not a valid ISO 3166-1 country name.
- **On failure:** quarantine and standardize the value (map to canonical ISO name).
- **Monitoring:** scheduled assertion run; alert on any non-ISO value appearing.

---

## Cross-table checks (referential integrity)

### Order customer exists (`orders_customer_id_exists.sqlx`)
- **Detects:** orders in `orders_cleaned` whose non-null `customer_id` has no match in `customers_cleaned` (orphaned foreign key, e.g. `C999`).
- **On failure:** investigate — an order pointing at an unknown customer means a missing dimension row or a bad key; it would lose its country in downstream marts.
- **Monitoring:** scheduled assertion run; trend the count of orphaned orders.

### Line item product exists (`order_items_product_id_exists.sqlx`)
- **Detects:** line items in `order_items_cleaned` whose non-null `product_id` has no match in `products_cleaned` (orphaned foreign key).
- **On failure:** investigate — an unmatched product means revenue would be dropped or land in an unknown category in `category_sales`.
- **Monitoring:** scheduled assertion run; trend the count of orphaned line items.
