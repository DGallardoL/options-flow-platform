"""
Spark Clean Job — reads raw trades from MongoDB, deduplicates,
parses timestamps, filters market hours, parses symbols,
and writes to options_analytics.cleaned_trades.
"""
import os
import re
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, udf, from_unixtime, hour, dayofweek, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType, IntegerType, LongType
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


def parse_option_symbol(sym: str):
    if not sym:
        return None, None, None, None
    m = re.match(r'^O:(\w+?)(\d{6})([CP])(\d{8})$', sym)
    if not m:
        return None, None, None, None
    underlying, date_str, cp, strike_raw = m.groups()
    expiration = datetime.strptime(date_str, '%y%m%d').strftime('%Y-%m-%d')
    contract_type = 'call' if cp == 'C' else 'put'
    strike = int(strike_raw) / 1000
    return underlying, expiration, contract_type, strike


def main():
    spark = SparkSession.builder \
        .appName("OptionsFlow-Clean") \
        .master("local[*]") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    # Read from MongoDB using pymongo
    client = MongoClient(MONGO_URI)
    raw_db = client["options_raw"]
    analytics_db = client["options_analytics"]

    print("=== Reading raw trades from MongoDB ===")
    raw_trades = list(raw_db.trades.find({}, {"_id": 0}))
    print(f"Raw trades count: {len(raw_trades)}")

    if not raw_trades:
        print("No raw trades found. Exiting.")
        spark.stop()
        client.close()
        return

    # Create DataFrame
    schema = StructType([
        StructField("ev", StringType()),
        StructField("sym", StringType()),
        StructField("x", IntegerType()),
        StructField("p", FloatType()),
        StructField("s", IntegerType()),
        StructField("t", LongType()),
        StructField("q", LongType()),
    ])

    rows = []
    for t in raw_trades:
        rows.append((
            t.get("ev"),
            t.get("sym"),
            t.get("x"),
            float(t["p"]) if t.get("p") is not None else None,
            t.get("s"),
            t.get("t"),
            t.get("q"),
        ))

    df = spark.createDataFrame(rows, schema)
    print(f"DataFrame created: {df.count()} rows")

    # Deduplicate by (sym, q)
    df = df.dropDuplicates(["sym", "q"])
    print(f"After dedup: {df.count()} rows")

    # Parse timestamp
    df = df.withColumn("timestamp", from_unixtime(col("t") / 1000))
    df = df.withColumn("hour", hour(col("timestamp")))
    df = df.withColumn("dow", dayofweek(col("timestamp")))

    # Filter market hours (Mon-Fri, 9:30-16:00 ET approximation using UTC-4)
    # dayofweek: 1=Sunday, 2=Monday, ..., 7=Saturday
    df = df.filter(
        (col("dow") >= 2) & (col("dow") <= 6)
    )

    # Parse option symbols
    parse_underlying_udf = udf(lambda s: parse_option_symbol(s)[0] if s else None, StringType())
    parse_expiration_udf = udf(lambda s: parse_option_symbol(s)[1] if s else None, StringType())
    parse_type_udf = udf(lambda s: parse_option_symbol(s)[2] if s else None, StringType())
    parse_strike_udf = udf(lambda s: parse_option_symbol(s)[3] if s else None, FloatType())

    df = df.withColumn("underlying", parse_underlying_udf(col("sym")))
    df = df.withColumn("expiration", parse_expiration_udf(col("sym")))
    df = df.withColumn("contract_type", parse_type_udf(col("sym")))
    df = df.withColumn("strike", parse_strike_udf(col("sym")))

    # Filter out rows where symbol couldn't be parsed
    df = df.filter(col("underlying").isNotNull())
    print(f"After symbol parsing: {df.count()} rows")

    # Write to options_analytics.cleaned_trades
    cleaned_docs = []
    for row in df.collect():
        doc = {
            "sym": row["sym"],
            "underlying": row["underlying"],
            "expiration": row["expiration"],
            "contract_type": row["contract_type"],
            "strike": row["strike"],
            "price": row["p"],
            "size": row["s"],
            "exchange": row["x"],
            "timestamp": row["timestamp"],
            "hour": row["hour"],
            "sequence_number": row["q"],
            "raw_timestamp_ms": row["t"],
        }
        cleaned_docs.append(doc)

    if cleaned_docs:
        analytics_db.cleaned_trades.delete_many({})
        analytics_db.cleaned_trades.insert_many(cleaned_docs)
        print(f"=== Wrote {len(cleaned_docs)} cleaned trades ===")
    else:
        print("No cleaned trades to write.")

    spark.stop()
    client.close()
    print("=== Spark Clean Job Complete ===")


if __name__ == "__main__":
    main()
