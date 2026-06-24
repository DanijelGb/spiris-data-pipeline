// Declare the raw BigQuery tables (loaded by the Python ingestion pipeline)
// so they can be referenced with ${ref("<table>")} downstream.

const RAW_TABLES = ["orders", "order_items", "customers", "products"];

RAW_TABLES.forEach((name) =>
    declare({
        schema: "raw",
        name,
    })
);
