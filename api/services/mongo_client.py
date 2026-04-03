"""Async MongoDB client using Motor."""
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_DASHBOARD_PWD = os.environ.get("MONGO_DASHBOARD_PWD", "dashboard_secure_2024")
MONGO_URI = (
    f"mongodb://dashboard_reader:{MONGO_DASHBOARD_PWD}"
    f"@localhost:27025/"
    f"?authSource=admin"
)

client = AsyncIOMotorClient(MONGO_URI)
analytics_db = client["options_analytics"]
raw_db = client["options_raw"]
