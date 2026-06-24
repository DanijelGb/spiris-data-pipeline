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
- A `loaded_at` UTC timestamp is added at load time for lineage/freshness.
- Data volume is small enough to load via `load_table_from_dataframe` (in-memory). Larger files would need a batched or GCS-staged load.

**Runtime**
- Python 3.9 with the pinned dependencies in `requirements.txt`.