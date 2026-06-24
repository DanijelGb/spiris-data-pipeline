# Spiris Data Pipeline

Loads the source CSVs into BigQuery (`raw`) with a Python ingestion job, then
transforms them through `staging` → `analytics` (star schema) → `datamart`
(business marts) with Dataform.

## Layers

| Dataset | Purpose |
|---|---|
| `raw` | Faithful mirror of the source CSVs (full-snapshot, schema inferred). |
| `staging` | Cleaned, typed, deduplicated tables. |
| `analytics` | Star schema: `fact_order_items`, `dim_customers`, `dim_products`. |
| `datamart` | Business marts: `orders_enriched`, `daily_sales`, `category_sales`. |

## Data model

The `analytics` layer uses a **dimensional model**, implemented specifically as a **star schema**: a central fact table surrounded by denormalized dimension tables, each one join away.

- **Fact:** `fact_order_items` — one row per order line item (the grain). It holds the measures (`quantity`, `price_per_unit`, `line_amount`) and the foreign keys to the dimensions, plus the order date/status as degenerate attributes.
- **Dimensions:** `dim_customers` and `dim_products` — the descriptive context (who bought, what was bought), kept flat (denormalized).

**Why a star schema (and not a snowflake)?**
A dimensional model is the methodology; a star schema is one physical shape of it (a central fact joined directly to flat dimensions). The main alternative, a *snowflake*, normalizes dimensions into sub-tables — e.g. splitting `category` out of `dim_products` into its own `dim_category` table joined by a key. I chose star because:

- **Fewer joins / simpler queries.** Every dimension is one hop from the fact, so analytical queries and the downstream marts stay simple and fast.
- **Storage is cheap on BigQuery; scan/join simplicity matters more.** Snowflake's main benefit (less redundancy) saves storage at the cost of extra joins — the wrong trade-off on a columnar, scan-priced warehouse.
- **Clear grain.** Modeling the fact at the line-item grain keeps measures additive and lets the marts aggregate cleanly (per order, per day, per category).

For example, `dim_products` keeps `product_id`, `product_name`, and `category` together in one table; a snowflake would split `category` into its own `dim_category` joined by a key. The star keeps that flat for one-hop access.

## Running

```bash
# 1. Ingest CSVs into raw (creates datasets if missing)
GCP_PROJECT=project-08bac5b8-2547-453b-a88 .venv/bin/python src/run_pipeline.py

# 2. Build the transformations
dataform run
```

## Assumptions about the target environment

**Platform & authentication**
- Target warehouse is **BigQuery**, location **EU**.
- The `GCP_PROJECT` environment variable must be set; `config.py` fails loudly if it is not.
- Authentication uses **Application Default Credentials** (`gcloud auth application-default login`). No service-account key is committed.

**Datasets & schema**
- The pipeline **creates the datasets** (`raw`, `staging`, `analytics`, `datamart`) on run, so they do not need to pre-exist (`create_dataset(..., exists_ok=True)`).
- Raw table schemas are **inferred** from the CSVs by pandas/BigQuery; no schema is enforced at the raw layer. Type and constraint enforcement happens in `staging`.

**Idempotency**
- Raw loads use **`WRITE_TRUNCATE`**, so each run fully replaces the table. Re-running produces the same result with no duplicates.
- Dataform models are rebuilt as tables, so transformations are idempotent as well.

**Source data**
- CSVs live in `data/` with filenames matching the table names in `config.py` (`orders`, `order_items`, `customers`, `products`).
- Data volume is small enough to load via `load_table_from_dataframe` (in-memory). Larger files would need a batched or GCS-staged load.

**Runtime**
- Python 3.9 with the pinned dependencies in `requirements.txt`.

## Scalability (thousands → billions of rows)

The current design favours simplicity at small volume: a full-snapshot `raw` layer, `WRITE_TRUNCATE` loads, and Dataform models rebuilt as full tables. At billions of rows that becomes slow and expensive, because every run rescans and rewrites the whole history. Here is how each concern would change.

**Storage & partitioning**
- Reintroduce an ingestion timestamp (a `loaded_at` / load-date column) on the raw and fact tables and **partition** on it (date/timestamp or ingestion-time partitioning). Partition pruning lets queries and incremental builds scan only the relevant days instead of the whole table — the single biggest lever on both compute and cost.
- Partition `fact_order_items` on `order_date`; partition large, frequently-loaded tables on their load date.
- **Cluster** each table on the columns most used in filters and joins — e.g. `fact_order_items` clustered by `product_id` / `customer_id`, `daily_sales` by `date`. Clustering co-locates related rows so scans read fewer blocks on top of partition pruning. The exact clustering keys would be chosen from observed query patterns.

**Incremental vs. full-refresh processing**
- Replace `WRITE_TRUNCATE` and full rebuilds with **incremental processing**. Raw ingestion appends new/changed partitions rather than overwriting the table.
- Dataform models become `type: "incremental"`, processing only rows newer than the last build (e.g. `WHERE loaded_at > (SELECT MAX(loaded_at) FROM self)`), so each run touches a small slice instead of recomputing all history.
- For dimensions that change over time (**SCD**), use a **`MERGE`** keyed on the natural key, updating/inserting based on the ingestion timestamp. This avoids the two bad extremes — a full rebuild (expensive, and needlessly rewrites unchanged history) and a naïve incremental append (which leaves stale or duplicate dimension rows). For full history (SCD type 2) the dimension would carry `valid_from` / `valid_to` ranges.
- Keep full-refresh only for small, cheap-to-rebuild tables (tiny lookups) where the incremental complexity isn't worth it.

**Compute & parallelism**
- BigQuery is serverless and auto-parallelises a single query across slots, so the goal is to **give it less work** (partition pruning, clustering, incremental slices) rather than to manage threads manually.
- Ingestion at scale moves from in-memory `load_table_from_dataframe` to **GCS-staged batch loads** (`load_table_from_uri`) or streaming inserts, which BigQuery ingests in parallel and which don't hold the whole file in one process's memory.
- The Dataform DAG already builds independent models (e.g. the three dimensions) **in parallel**; with partitioned incrementals each model also processes far less data, and large backfills can be parallelised per-partition.

**Cost trade-offs**
- On-demand BigQuery bills by **bytes scanned**, so partitioning, clustering, and incremental builds cut cost directly, not just runtime.
- The trade-off is complexity: incremental + `MERGE` introduces state to manage (watermarks, late-arriving data, reprocessing) versus the simplicity of full rebuilds; keeping history (SCD2, long retention) costs more storage but enables point-in-time analysis.
- Operationally, **flat-rate / slot reservations** become cheaper than on-demand past a steady volume, and partition expiration plus tiered storage control long-term storage cost.
- Rule of thumb: pay the complexity cost only where data volume justifies it, and keep small tables simple.