from google.cloud import bigquery

from config import PROJECT_ID, DATASETS

client = bigquery.Client(project=PROJECT_ID)


def create_datasets() -> None:
    for dataset_name in DATASETS:
        dataset_id = f"{client.project}.{dataset_name}"

        dataset = bigquery.Dataset(dataset_id)
        dataset.location = "EU"

        client.create_dataset(dataset, exists_ok=True)

        print(f"Dataset {dataset_id} ready")


if __name__ == "__main__":
    create_datasets()