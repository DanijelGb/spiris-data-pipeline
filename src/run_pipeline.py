from create_datasets import create_datasets
from ingest import ingest_csvs

def main():
    create_datasets()
    ingest_csvs()

if __name__ == "__main__":
    main()