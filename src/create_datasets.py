from google.cloud import bigquery

client = bigquery.Client()

datasets = ["staging", "analytics"]

for dataset_name in datasets:
    dataset_id = f"{client.project}.{dataset_name}"

    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "EU"

    dataset = client.create_dataset(
        dataset,
        exists_ok=True
    )

    print(f"Dataset {dataset_id} ready")