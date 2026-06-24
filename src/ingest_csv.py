from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from google.cloud import bigquery

from config import PROJECT_ID, RAW_DATASET, TABLES

client = bigquery.Client(project=PROJECT_ID)
    

def load_csv(table_name: str) -> None:
    file_path = Path("data") / f"{table_name}.csv"

    df = pd.read_csv(file_path)
    df["loaded_at"] = datetime.now(tz=timezone.utc)

    table_id = f"{client.project}.{RAW_DATASET}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_TRUNCATE"
    )

    load_job = client.load_table_from_dataframe(
        df,
        table_id,
        job_config=job_config
    )

    load_job.result()

    print(f"Loaded {table_name}")


def ingest_csv() -> None:
    for table in TABLES:
        load_csv(table)


if __name__ == "__main__":
    ingest_csv()
