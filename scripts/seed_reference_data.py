"""
Seed reference data — loads sectors.csv into MongoDB for reference.
"""
import os
import csv
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_ADMIN_PWD = os.environ.get("MONGO_ADMIN_PWD", "admin_secure_2024")
MONGO_URI = (
    f"mongodb://admin:{MONGO_ADMIN_PWD}"
    f"@localhost:27025/"
    f"?authSource=admin"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTORS_PATH = os.path.join(BASE_DIR, "data", "sectors.csv")


def main():
    client = MongoClient(MONGO_URI)
    db = client["options_raw"]

    with open(SECTORS_PATH) as f:
        reader = csv.DictReader(f)
        sectors = list(reader)

    db.sectors.drop()
    db.sectors.insert_many(sectors)
    print(f"Seeded {len(sectors)} sector records")

    client.close()


if __name__ == "__main__":
    main()
