"""
Load Test — generates synthetic option trade docs and inserts them
at varying rates (10/50/100/500 docs/sec) for 30s each,
measuring latency and throughput.
"""
import os
import time
import random
import string
from datetime import datetime, timezone

from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_INGEST_PWD = os.environ.get("MONGO_INGEST_PWD", "ingest_secure_2024")
MONGO_URI = (
    f"mongodb://ingest_writer:{MONGO_INGEST_PWD}"
    f"@localhost:27025/"
    f"?authSource=admin"
)

TICKERS = ["AAPL", "NVDA", "TSLA", "SPY", "AMZN", "META", "MSFT", "GOOGL", "QQQ", "AMD"]
DURATION = 30  # seconds per rate
RATES = [10, 50, 100, 500]


def generate_trade_doc(seq: int) -> dict:
    ticker = random.choice(TICKERS)
    cp = random.choice(["C", "P"])
    strike = random.randint(50, 500) * 1000
    date_str = "251219"
    sym = f"O:{ticker}{date_str}{cp}{strike:08d}"

    return {
        "ev": "T",
        "sym": sym,
        "x": random.randint(300, 320),
        "p": round(random.uniform(0.01, 50.0), 2),
        "s": random.randint(1, 1000),
        "c": [random.randint(0, 50)],
        "t": int(time.time() * 1000),
        "q": seq,
        "_ingested_at": datetime.now(timezone.utc),
    }


def run_load_test():
    client = MongoClient(MONGO_URI)
    db = client["options_raw"]
    collection = db["load_test_trades"]

    # Clean up previous test data
    collection.drop()

    results = []
    seq = 0

    print(f"{'Rate':>10} | {'Target':>8} | {'Inserted':>10} | {'Avg Latency':>12} | {'Throughput':>12}")
    print("-" * 70)

    for rate in RATES:
        latencies = []
        inserted = 0
        start_time = time.time()
        interval = 1.0 / rate

        while time.time() - start_time < DURATION:
            batch_start = time.time()

            doc = generate_trade_doc(seq)
            seq += 1

            t0 = time.time()
            collection.insert_one(doc)
            latency = (time.time() - t0) * 1000  # ms
            latencies.append(latency)
            inserted += 1

            # Sleep to maintain rate
            elapsed = time.time() - batch_start
            if elapsed < interval:
                time.sleep(interval - elapsed)

        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        actual_throughput = inserted / DURATION

        result = {
            "rate": rate,
            "target": rate * DURATION,
            "inserted": inserted,
            "avg_latency_ms": round(avg_latency, 2),
            "throughput_per_sec": round(actual_throughput, 1),
        }
        results.append(result)

        print(f"{rate:>10} | {rate * DURATION:>8} | {inserted:>10} | {avg_latency:>10.2f}ms | {actual_throughput:>10.1f}/s")

    # Write CSV
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "load_test_results.csv")
    with open(csv_path, "w") as f:
        f.write("rate,target,inserted,avg_latency_ms,throughput_per_sec\n")
        for r in results:
            f.write(f"{r['rate']},{r['target']},{r['inserted']},{r['avg_latency_ms']},{r['throughput_per_sec']}\n")

    print(f"\nResults saved to {csv_path}")

    # Cleanup
    collection.drop()
    client.close()


if __name__ == "__main__":
    print("=== MongoDB Load Test ===")
    print(f"Duration per rate: {DURATION}s")
    print(f"Rates: {RATES} docs/sec\n")
    run_load_test()
