from create_datasets import create_datasets
from ingest_csv import ingest_csv

def main():
    create_datasets()
    ingest_csv()

if __name__ == "__main__":
    main()