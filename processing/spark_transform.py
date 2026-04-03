"""
Spark Transform Job — reads enriched trades, aggregates by
(underlying, sector, date, hour), computes analytics metrics,
and writes to options_analytics.aggregated_metrics.
"""
import os
from datetime import datetime

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, sum as spark_sum, avg, count, when, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, FloatType,
    IntegerType, BooleanType
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


def main():
    spark = SparkSession.builder \
        .appName("OptionsFlow-Transform") \
        .master("local[*]") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    client = MongoClient(MONGO_URI)
    analytics_db = client["options_analytics"]

    # Read enriched trades
    enriched = list(analytics_db.enriched_trades.find({}, {"_id": 0}))
    print(f"Enriched trades: {len(enriched)}")

    if not enriched:
        print("No enriched trades found. Exiting.")
        spark.stop()
        client.close()
        return

    # Prepare rows for DataFrame
    rows = []
    for t in enriched:
        ts = t.get("timestamp")
        if isinstance(ts, str):
            try:
                dt = datetime.fromisoformat(ts)
                date_str = dt.strftime("%Y-%m-%d")
                hour_val = dt.hour
            except (ValueError, TypeError):
                date_str = "unknown"
                hour_val = 0
        elif isinstance(ts, datetime):
            date_str = ts.strftime("%Y-%m-%d")
            hour_val = ts.hour
        else:
            date_str = "unknown"
            hour_val = t.get("hour", 0) or 0

        rows.append((
            t.get("underlying", ""),
            t.get("sector", "Unknown"),
            date_str,
            hour_val,
            t.get("contract_type", ""),
            float(t.get("size", 0) or 0),
            float(t.get("dollar_volume", 0) or 0),
            float(t.get("implied_volatility") or 0),
            float(t.get("gamma") or 0),
            float(t.get("open_interest") or 0),
            float(t.get("underlying_price") or 0),
            float(t.get("bid_ask_spread") or 0),
            bool(t.get("unusual_flag", False)),
            float(t.get("delta") or 0),
        ))

    schema = StructType([
        StructField("underlying", StringType()),
        StructField("sector", StringType()),
        StructField("date", StringType()),
        StructField("hour", IntegerType()),
        StructField("contract_type", StringType()),
        StructField("size", FloatType()),
        StructField("dollar_volume", FloatType()),
        StructField("implied_volatility", FloatType()),
        StructField("gamma", FloatType()),
        StructField("open_interest", FloatType()),
        StructField("underlying_price", FloatType()),
        StructField("bid_ask_spread", FloatType()),
        StructField("unusual_flag", BooleanType()),
        StructField("delta", FloatType()),
    ])

    df = spark.createDataFrame(rows, schema)

    # Aggregations by (underlying, sector, date, hour)
    agg_df = df.groupBy("underlying", "sector", "date", "hour").agg(
        spark_sum(when(col("contract_type") == "call", col("size")).otherwise(0)).alias("total_call_volume"),
        spark_sum(when(col("contract_type") == "put", col("size")).otherwise(0)).alias("total_put_volume"),
        avg(when(col("contract_type") == "call", col("implied_volatility"))).alias("avg_iv_calls"),
        avg(when(col("contract_type") == "put", col("implied_volatility"))).alias("avg_iv_puts"),
        spark_sum(col("dollar_volume")).alias("total_dollar_volume"),
        avg(col("bid_ask_spread")).alias("avg_bid_ask_spread"),
        count(when(col("unusual_flag") == True, True)).alias("unusual_activity_count"),
        # Gamma exposure: sum(gamma * OI * 100 * spot^2) for calls and puts
        spark_sum(
            when(col("contract_type") == "call",
                 col("gamma") * col("open_interest") * 100 * col("underlying_price") * col("underlying_price"))
            .otherwise(0)
        ).alias("call_gamma_exposure"),
        spark_sum(
            when(col("contract_type") == "put",
                 -col("gamma") * col("open_interest") * 100 * col("underlying_price") * col("underlying_price"))
            .otherwise(0)
        ).alias("put_gamma_exposure"),
    )

    # Compute derived columns
    agg_df = agg_df.withColumn(
        "put_call_ratio",
        when(col("total_call_volume") > 0,
             col("total_put_volume") / col("total_call_volume"))
        .otherwise(0)
    )
    agg_df = agg_df.withColumn(
        "iv_skew",
        col("avg_iv_puts") - col("avg_iv_calls")
    )
    agg_df = agg_df.withColumn(
        "net_gamma_exposure",
        col("call_gamma_exposure") + col("put_gamma_exposure")
    )

    # Collect and write to MongoDB
    agg_docs = []
    for row in agg_df.collect():
        doc = row.asDict()
        # Convert NaN/None
        for k, v in doc.items():
            if v != v:  # NaN check
                doc[k] = None
        agg_docs.append(doc)

    if agg_docs:
        analytics_db.aggregated_metrics.delete_many({})
        analytics_db.aggregated_metrics.insert_many(agg_docs)
        print(f"=== Wrote {len(agg_docs)} aggregated metrics ===")

        # Recreate indexes
        analytics_db.aggregated_metrics.create_index([("underlying", 1), ("date", -1), ("hour", 1)])
        analytics_db.aggregated_metrics.create_index([("sector", 1), ("date", -1)])
    else:
        print("No aggregated metrics to write.")

    spark.stop()
    client.close()
    print("=== Spark Transform Job Complete ===")


if __name__ == "__main__":
    main()
