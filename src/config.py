import os

PROJECT_ID = os.environ["GCP_PROJECT"]   # fail loudly if not set
RAW_DATASET = "raw"
TABLES = ["orders", "order_items", "customers", "products"]