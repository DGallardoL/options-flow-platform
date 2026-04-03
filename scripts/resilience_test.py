"""
Resilience Test — continuously inserts docs while stopping/starting
MongoDB shard replica set members, verifying writes survive across
shard failures and the sharded cluster recovers automatically.

Architecture under test:
  Shard 1 (rs0): mongo1, mongo2, mongo3
  Shard 2 (rs1): mongo4, mongo5, mongo6
  Config Server: configsvr1
  Router: mongos (port 27025)
"""
import os
import time
import subprocess
import threading
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, AutoReconnect
from dotenv import load_dotenv

load_dotenv()

MONGO_INGEST_PWD = os.environ.get("MONGO_INGEST_PWD", "ingest_secure_2024")
MONGO_URI = (
    f"mongodb://ingest_writer:{MONGO_INGEST_PWD}"
    f"@localhost:27025/"
    f"?authSource=admin&w=majority&wtimeoutMS=5000"
    f"&serverSelectionTimeoutMS=5000"
)


def docker_stop(container: str):
    print(f"  [ACTION] Stopping {container}...")
    subprocess.run(["docker", "stop", container], capture_output=True)
    print(f"  [ACTION] {container} stopped")


def docker_start(container: str):
    print(f"  [ACTION] Starting {container}...")
    subprocess.run(["docker", "start", container], capture_output=True)
    print(f"  [ACTION] {container} started")


def insert_continuously(client, db_name, stop_event, results):
    """Insert docs continuously until stop_event is set."""
    db = client[db_name]
    collection = db["resilience_test"]
    seq = 0
    while not stop_event.is_set():
        try:
            doc = {
                "seq": seq,
                "t": int(time.time() * 1000),
                "_ingested_at": datetime.now(timezone.utc),
            }
            collection.insert_one(doc)
            results["success"] += 1
            seq += 1
        except (ServerSelectionTimeoutError, AutoReconnect) as e:
            results["failures"] += 1
            results["errors"].append(str(e)[:100])
        except Exception as e:
            results["failures"] += 1
            results["errors"].append(str(e)[:100])

        time.sleep(0.1)


def run_resilience_test():
    client = MongoClient(MONGO_URI)
    db = client["options_raw"]

    # Clean up
    try:
        db.resilience_test.drop()
    except Exception:
        pass

    results = {"success": 0, "failures": 0, "errors": []}
    stop_event = threading.Event()

    # Start continuous inserts
    insert_thread = threading.Thread(
        target=insert_continuously,
        args=(client, "options_raw", stop_event, results)
    )
    insert_thread.start()

    # === PHASE 1: Baseline ===
    print("\n--- Phase 1: Normal operation (10s) ---")
    time.sleep(10)
    phase1 = results["success"]
    print(f"  Successful writes: {phase1}")
    print(f"  Rate: {phase1/10:.1f} writes/sec")

    # === PHASE 2: Kill one secondary from Shard 1 ===
    print("\n--- Phase 2: Stop mongo2 (rs0 secondary, Shard 1) ---")
    docker_stop("mongo2")
    time.sleep(15)
    phase2 = results["success"] - phase1
    print(f"  Writes with 1 secondary down: {phase2}")
    print(f"  Failures: {results['failures']}")
    print("  (Expected: writes continue — majority still available)")

    # === PHASE 3: Kill one secondary from Shard 2 simultaneously ===
    print("\n--- Phase 3: Also stop mongo5 (rs1 secondary, Shard 2) ---")
    docker_stop("mongo5")
    time.sleep(15)
    phase3_start = results["success"]
    phase3 = phase3_start - phase1 - phase2
    print(f"  Writes with 1 secondary down per shard: {phase3}")
    print(f"  Failures: {results['failures']}")
    print("  (Expected: writes continue — each shard still has majority)")

    # === PHASE 4: Kill ANOTHER secondary from Shard 1 — no majority! ===
    print("\n--- Phase 4: Stop mongo3 (rs0 loses majority!) ---")
    docker_stop("mongo3")
    time.sleep(15)
    phase4 = results["success"] - phase3_start
    failures_phase4 = results["failures"]
    print(f"  Writes during rs0 without majority: {phase4}")
    print(f"  Total failures: {failures_phase4}")
    print("  (Expected: writes to Shard 1 fail — no majority on rs0)")

    # === PHASE 5: Restore all downed nodes ===
    print("\n--- Phase 5: Restart mongo2 + mongo3 + mongo5 ---")
    docker_start("mongo2")
    docker_start("mongo3")
    docker_start("mongo5")
    print("  Waiting for recovery (25s)...")
    time.sleep(25)
    phase5_start = results["success"]
    time.sleep(10)
    phase5 = results["success"] - phase5_start
    print(f"  Writes after full recovery: {phase5}")
    print(f"  Rate: {phase5/10:.1f} writes/sec")

    stop_event.set()
    insert_thread.join(timeout=5)

    # === Summary ===
    total_count = 0
    try:
        total_count = db.resilience_test.count_documents({})
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("SHARDED CLUSTER RESILIENCE TEST SUMMARY")
    print("=" * 60)
    print(f"  Architecture: 2 shards (rs0 + rs1) via mongos:27025")
    print(f"  Total successful writes: {results['success']}")
    print(f"  Total failures:          {results['failures']}")
    print(f"  Docs in collection:      {total_count}")
    print(f"  Data integrity:          {'PASS' if total_count == results['success'] else 'CHECK'}")
    print(f"  Partial failure recovery: {'PASS' if phase3 > 0 else 'FAIL'}")
    print(f"  Full recovery:            {'PASS' if phase5 > 0 else 'FAIL'}")
    print("")
    print("  Phase results:")
    print(f"    Normal:                {phase1} writes")
    print(f"    1 secondary/shard down: {phase2} writes")
    print(f"    2 secondaries down:     {phase3} writes")
    print(f"    No majority (rs0):      {phase4} writes (failures expected)")
    print(f"    After recovery:         {phase5} writes")

    if results["errors"]:
        unique_errors = list(set(results["errors"][:10]))
        print(f"\n  Sample errors ({len(unique_errors)}):")
        for e in unique_errors[:5]:
            print(f"    - {e}")

    # Cleanup
    try:
        db.resilience_test.drop()
    except Exception:
        pass
    client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("  MongoDB Sharded Cluster Resilience Test")
    print("=" * 60)
    print("  This test will stop/start MongoDB containers.")
    print("  Make sure the sharded cluster is running.")
    print("  Containers: mongo1-6, configsvr1, mongos")
    print("")
    run_resilience_test()
