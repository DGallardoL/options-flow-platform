"""
Spark Enrich Job — reads cleaned trades + snapshots, joins to add
Greeks/IV/OI, joins with sectors.csv, computes derived fields,
and writes to options_analytics.enriched_trades.
"""
import os
import csv

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, lit, when, abs as spark_abs
)
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType,
    IntegerType, LongType, BooleanType
)
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_SPARK_PWD = os.environ.get("MONGO_SPARK_PWD", "spark_secure_2024")
MONGO_URI = (
    f"mongodb://spark_processor:{MONGO_SPARK_PWD}"
    f"@localhost:27025/"
    f"?authSource=admin"
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTORS_PATH = os.path.join(BASE_DIR, "data", "sectors.csv")


def load_sectors() -> dict:
    """Load sectors.csv into a dict: ticker -> {sector, industry}."""
    sectors = {}
    with open(SECTORS_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sectors[row["ticker"]] = {
                "sector": row["sector"],
                "industry": row["industry"],
            }
    return sectors


def get_latest_snapshot(raw_db, sym: str) -> dict | None:
    """Get the most recent snapshot for a given option symbol."""
    snap = raw_db.snapshots.find_one(
        {"sym": sym},
        sort=[("fetched_at", -1)]
    )
    return snap


def main():
    spark = SparkSession.builder \
        .appName("OptionsFlow-Enrich") \
        .master("local[*]") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    client = MongoClient(MONGO_URI)
    raw_db = client["options_raw"]
    analytics_db = client["options_analytics"]

    # Load sectors
    sectors = load_sectors()
    print(f"Loaded {len(sectors)} sector mappings")

    # Read cleaned trades
    cleaned = list(analytics_db.cleaned_trades.find({}, {"_id": 0}))
    print(f"Cleaned trades: {len(cleaned)}")

    if not cleaned:
        print("No cleaned trades found. Exiting.")
        spark.stop()
        client.close()
        return

    # Build snapshot cache: sym -> latest snapshot
    snapshot_cache = {}
    unique_syms = set(t["sym"] for t in cleaned)
    print(f"Fetching snapshots for {len(unique_syms)} unique symbols...")

    for sym in unique_syms:
        snap = get_latest_snapshot(raw_db, sym)
        if snap:
            snapshot_cache[sym] = snap

    print(f"Found snapshots for {len(snapshot_cache)} symbols")

    # Enrich each trade
    enriched_docs = []
    for trade in cleaned:
        sym = trade["sym"]
        underlying = trade.get("underlying", "")
        snap = snapshot_cache.get(sym)

        # Greeks & IV from snapshot
        greeks = snap.get("greeks", {}) if snap else {}
        delta = greeks.get("delta")
        gamma = greeks.get("gamma")
        theta = greeks.get("theta")
        vega = greeks.get("vega")
        iv = snap.get("implied_volatility") if snap else None
        oi = snap.get("open_interest", 0) if snap else 0
        last_quote = snap.get("last_quote", {}) if snap else {}
        bid = last_quote.get("bid")
        ask = last_quote.get("ask")
        underlying_asset = snap.get("underlying_asset", {}) if snap else {}
        underlying_price = underlying_asset.get("price")

        # Sector info
        sector_info = sectors.get(underlying, {})
        sector = sector_info.get("sector", "Unknown")
        industry = sector_info.get("industry", "Unknown")

        # Derived calculations
        price = trade.get("price", 0) or 0
        size = trade.get("size", 0) or 0
        dollar_volume = price * size * 100
        strike = trade.get("strike", 0) or 0

        # Moneyness
        moneyness_pct = None
        moneyness = "Unknown"
        if underlying_price and underlying_price > 0:
            moneyness_pct = (strike - underlying_price) / underlying_price
            abs_m = abs(moneyness_pct)
            ct = trade.get("contract_type", "call")
            if ct == "call":
                if moneyness_pct < -0.10:
                    moneyness = "Deep ITM"
                elif moneyness_pct < -0.02:
                    moneyness = "ITM"
                elif abs_m <= 0.02:
                    moneyness = "ATM"
                elif moneyness_pct < 0.10:
                    moneyness = "OTM"
                else:
                    moneyness = "Deep OTM"
            else:
                if moneyness_pct > 0.10:
                    moneyness = "Deep ITM"
                elif moneyness_pct > 0.02:
                    moneyness = "ITM"
                elif abs_m <= 0.02:
                    moneyness = "ATM"
                elif moneyness_pct > -0.10:
                    moneyness = "OTM"
                else:
                    moneyness = "Deep OTM"

        # Bid-ask spread
        bid_ask_spread = (ask - bid) if (ask is not None and bid is not None) else None

        # Vol/OI ratio
        oi_safe = max(oi or 0, 1)
        vol_oi_ratio = size / oi_safe
        unusual_flag = vol_oi_ratio > 1.5

        # Sentiment heuristic
        ct = trade.get("contract_type", "call")
        if ct == "call" and moneyness in ("OTM", "Deep OTM"):
            sentiment = "Bullish"
        elif ct == "put" and moneyness in ("OTM", "Deep OTM"):
            sentiment = "Bearish"
        elif ct == "call" and moneyness in ("ITM", "Deep ITM"):
            sentiment = "Bullish"
        elif ct == "put" and moneyness in ("ITM", "Deep ITM"):
            sentiment = "Bearish"
        else:
            sentiment = "Neutral"

        doc = {
            **trade,
            "delta": delta,
            "gamma": gamma,
            "theta": theta,
            "vega": vega,
            "implied_volatility": iv,
            "open_interest": oi,
            "bid": bid,
            "ask": ask,
            "underlying_price": underlying_price,
            "sector": sector,
            "industry": industry,
            "dollar_volume": dollar_volume,
            "moneyness_pct": moneyness_pct,
            "moneyness": moneyness,
            "bid_ask_spread": bid_ask_spread,
            "vol_oi_ratio": vol_oi_ratio,
            "unusual_flag": unusual_flag,
            "sentiment": sentiment,
        }
        enriched_docs.append(doc)

    if enriched_docs:
        analytics_db.enriched_trades.delete_many({})
        analytics_db.enriched_trades.insert_many(enriched_docs)
        print(f"=== Wrote {len(enriched_docs)} enriched trades ===")

        # Recreate indexes
        analytics_db.enriched_trades.create_index([("underlying", 1), ("timestamp", -1)])
        analytics_db.enriched_trades.create_index([("sector", 1), ("timestamp", -1)])
        analytics_db.enriched_trades.create_index([("unusual_flag", 1), ("timestamp", -1)])
    else:
        print("No enriched trades to write.")

    spark.stop()
    client.close()
    print("=== Spark Enrich Job Complete ===")


if __name__ == "__main__":
    main()
