#!/bin/bash
set -e

# Load .env variables
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "============================================================"
echo "  Options Flow Intelligence Platform — Setup"
echo "  MongoDB Sharded Cluster + Full Pipeline"
echo "============================================================"

# ────────────────────────────────────────────────────────
# 1. Check prerequisites
# ────────────────────────────────────────────────────────
echo ""
echo "[1/7] Checking prerequisites..."
command -v docker >/dev/null 2>&1 || { echo "ERROR: Docker is required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: Python 3 is required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js is required"; exit 1; }
echo "  OK — Docker, Python, Node.js found"

# ────────────────────────────────────────────────────────
# 2. Check .env
# ────────────────────────────────────────────────────────
echo ""
echo "[2/7] Checking environment..."
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in values."
    exit 1
fi
if [ -z "$POLYGON_API_KEY" ]; then
    echo "WARNING: POLYGON_API_KEY not set in .env"
fi
echo "  OK — .env loaded"

# ────────────────────────────────────────────────────────
# 3. Install Python dependencies
# ────────────────────────────────────────────────────────
echo ""
echo "[3/7] Installing Python dependencies..."
pip install -r requirements.txt --quiet
echo "  OK"

# ────────────────────────────────────────────────────────
# 4. Generate MongoDB keyfile
# ────────────────────────────────────────────────────────
echo ""
echo "[4/7] Generating MongoDB keyfile..."
if [ ! -f docker/mongo/keyfile ]; then
    openssl rand -base64 756 > docker/mongo/keyfile
    chmod 400 docker/mongo/keyfile
    echo "  OK — Keyfile generated"
else
    echo "  OK — Keyfile already exists"
fi

# ────────────────────────────────────────────────────────
# 5. Start Docker containers
# ────────────────────────────────────────────────────────
echo ""
echo "[5/7] Starting MongoDB sharded cluster..."
echo "  Architecture:"
echo "    Config Server: configsvr1:27100"
echo "    Shard 1 (rs0): mongo1:27017, mongo2:27018, mongo3:27019"
echo "    Shard 2 (rs1): mongo4:27020, mongo5:27021, mongo6:27022"
echo "    Mongos Router: mongos:27025"
echo ""
docker compose up -d
echo ""
echo "  Waiting for all containers to be healthy (30s)..."
sleep 30

# ────────────────────────────────────────────────────────
# 6. Initialize sharded cluster
#    NOTE: All commands use 'docker exec' to run INSIDE
#    the containers. This is required because MongoDB's
#    localhost exception only allows the first admin user
#    to be created from localhost connections.
# ────────────────────────────────────────────────────────
echo ""
echo "[6/7] Initializing sharded cluster..."

# --- 6a. Init Config Server Replica Set ---
echo ""
echo "  [6a] Initiating config server replica set (configrs)..."
docker exec configsvr1 mongosh --port 27100 --quiet --eval '
rs.initiate({
  _id: "configrs",
  configsvr: true,
  members: [ { _id: 0, host: "configsvr1:27100" } ]
});
'
echo "  Waiting for config server primary..."
sleep 5
for i in $(seq 1 20); do
    IS_PRIMARY=$(docker exec configsvr1 mongosh --port 27100 --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null || echo "false")
    if [ "$IS_PRIMARY" = "true" ]; then
        echo "  OK — Config server primary elected"
        break
    fi
    sleep 2
done

# --- 6b. Init Shard 1 Replica Set (rs0) ---
echo ""
echo "  [6b] Initiating Shard 1 replica set (rs0)..."
docker exec mongo1 mongosh --port 27017 --quiet --eval '
rs.initiate({
  _id: "rs0",
  members: [
    { _id: 0, host: "mongo1:27017", priority: 2 },
    { _id: 1, host: "mongo2:27018" },
    { _id: 2, host: "mongo3:27019" }
  ]
});
'
echo "  Waiting for rs0 primary..."
sleep 5
for i in $(seq 1 30); do
    IS_PRIMARY=$(docker exec mongo1 mongosh --port 27017 --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null || echo "false")
    if [ "$IS_PRIMARY" = "true" ]; then
        echo "  OK — rs0 primary elected on mongo1"
        break
    fi
    sleep 2
done

# --- 6c. Init Shard 2 Replica Set (rs1) ---
echo ""
echo "  [6c] Initiating Shard 2 replica set (rs1)..."
docker exec mongo4 mongosh --port 27020 --quiet --eval '
rs.initiate({
  _id: "rs1",
  members: [
    { _id: 0, host: "mongo4:27020", priority: 2 },
    { _id: 1, host: "mongo5:27021" },
    { _id: 2, host: "mongo6:27022" }
  ]
});
'
echo "  Waiting for rs1 primary..."
sleep 5
for i in $(seq 1 30); do
    IS_PRIMARY=$(docker exec mongo4 mongosh --port 27020 --quiet --eval 'rs.isMaster().ismaster' 2>/dev/null || echo "false")
    if [ "$IS_PRIMARY" = "true" ]; then
        echo "  OK — rs1 primary elected on mongo4"
        break
    fi
    sleep 2
done

# --- 6d. Create admin user on mongos (localhost exception) ---
echo ""
echo "  [6d] Creating admin user on mongos (localhost exception)..."
sleep 10
docker exec mongos mongosh --port 27025 --quiet --eval "
db = db.getSiblingDB('admin');
db.createUser({
  user: 'admin',
  pwd: '${MONGO_ADMIN_PWD}',
  roles: [{ role: 'root', db: 'admin' }]
});
print('Admin user created');
"

# --- 6e. Add shards to cluster ---
echo ""
echo "  [6e] Adding shards to cluster..."
docker exec mongos mongosh --port 27025 --quiet \
    -u admin -p "${MONGO_ADMIN_PWD}" --authenticationDatabase admin --eval '
sh.addShard("rs0/mongo1:27017,mongo2:27018,mongo3:27019");
sh.addShard("rs1/mongo4:27020,mongo5:27021,mongo6:27022");
print("Shards added successfully");
'

# --- 6f. Enable sharding on databases and shard collections ---
echo ""
echo "  [6f] Enabling sharding on databases and collections..."
docker exec mongos mongosh --port 27025 --quiet \
    -u admin -p "${MONGO_ADMIN_PWD}" --authenticationDatabase admin --eval '

// Enable sharding on both databases
sh.enableSharding("options_raw");
sh.enableSharding("options_analytics");

// --- options_raw ---
db = db.getSiblingDB("options_raw");
db.createCollection("trades");
db.createCollection("quotes");
db.createCollection("aggregates");
db.createCollection("snapshots");

// Shard by sym (hashed) — distributes evenly across option tickers
db.trades.createIndex({ sym: "hashed" });
sh.shardCollection("options_raw.trades", { sym: "hashed" });

db.quotes.createIndex({ sym: "hashed" });
sh.shardCollection("options_raw.quotes", { sym: "hashed" });

db.aggregates.createIndex({ sym: "hashed" });
sh.shardCollection("options_raw.aggregates", { sym: "hashed" });

// Shard snapshots by underlying (hashed)
db.snapshots.createIndex({ underlying: "hashed" });
sh.shardCollection("options_raw.snapshots", { underlying: "hashed" });

// --- options_analytics ---
db = db.getSiblingDB("options_analytics");
db.createCollection("cleaned_trades");
db.createCollection("enriched_trades");
db.createCollection("aggregated_metrics");

db.enriched_trades.createIndex({ underlying: "hashed" });
sh.shardCollection("options_analytics.enriched_trades", { underlying: "hashed" });

db.aggregated_metrics.createIndex({ underlying: "hashed" });
sh.shardCollection("options_analytics.aggregated_metrics", { underlying: "hashed" });

print("Sharding configured for all collections");
'

# --- 6g. Create RBAC users ---
echo ""
echo "  [6g] Creating application users (RBAC)..."
docker exec mongos mongosh --port 27025 --quiet \
    -u admin -p "${MONGO_ADMIN_PWD}" --authenticationDatabase admin --eval "
db = db.getSiblingDB('admin');

db.createUser({
  user: 'ingest_writer',
  pwd: '${MONGO_INGEST_PWD}',
  roles: [{ role: 'readWrite', db: 'options_raw' }]
});

db.createUser({
  user: 'spark_processor',
  pwd: '${MONGO_SPARK_PWD}',
  roles: [
    { role: 'read', db: 'options_raw' },
    { role: 'readWrite', db: 'options_analytics' }
  ]
});

db.createUser({
  user: 'dashboard_reader',
  pwd: '${MONGO_DASHBOARD_PWD}',
  roles: [
    { role: 'read', db: 'options_analytics' },
    { role: 'read', db: 'options_raw' }
  ]
});

print('RBAC users created: ingest_writer, spark_processor, dashboard_reader');
"

# --- 6h. Create indexes ---
echo ""
echo "  [6h] Creating indexes..."
docker exec mongos mongosh --port 27025 --quiet \
    -u admin -p "${MONGO_ADMIN_PWD}" --authenticationDatabase admin --eval '

// === options_raw indexes ===
db = db.getSiblingDB("options_raw");

db.trades.createIndex({ sym: 1, t: -1 });
db.trades.createIndex({ t: -1 });
db.trades.createIndex({ sym: 1, q: 1 }, { unique: true });

db.quotes.createIndex({ sym: 1, t: -1 });
db.quotes.createIndex({ t: -1 });

db.aggregates.createIndex({ sym: 1, s: -1 });

db.snapshots.createIndex({ sym: 1, fetched_at: -1 });
db.snapshots.createIndex({ underlying: 1, fetched_at: -1 });

// === options_analytics indexes ===
db = db.getSiblingDB("options_analytics");

db.enriched_trades.createIndex({ underlying: 1, timestamp: -1 });
db.enriched_trades.createIndex({ sector: 1, timestamp: -1 });
db.enriched_trades.createIndex({ unusual_flag: 1, timestamp: -1 });

db.aggregated_metrics.createIndex({ underlying: 1, date: -1, hour: 1 });
db.aggregated_metrics.createIndex({ sector: 1, date: -1 });

print("All indexes created");
'

# --- 6i. Verify cluster ---
echo ""
echo "  [6i] Verifying cluster status..."
docker exec mongos mongosh --port 27025 --quiet \
    -u admin -p "${MONGO_ADMIN_PWD}" --authenticationDatabase admin --eval '
const status = sh.status();
print("  Shards: " + status.shards.length);
status.shards.forEach(s => print("    " + s._id + " → " + s.host));
print("  Databases sharded: options_raw, options_analytics");
' || echo "  WARNING: Could not verify (cluster may still be converging)"

echo ""
echo "  OK — Sharded cluster initialized"

# ────────────────────────────────────────────────────────
# 7. Install dashboard dependencies
# ────────────────────────────────────────────────────────
echo ""
echo "[7/7] Installing dashboard dependencies..."
cd dashboard && npm install --silent 2>/dev/null && cd ..
echo "  OK"

echo ""
echo "============================================================"
echo "  Setup complete!"
echo "============================================================"
echo ""
echo "  Cluster:    mongos router at localhost:27025"
echo "  Shards:     rs0 (mongo1-3) + rs1 (mongo4-6)"
echo "  Config:     configsvr1:27100"
echo "  Auth:       keyFile + RBAC (4 users)"
echo ""
echo "  Next steps:"
echo ""
echo "  1. Start data ingestion (2 terminals):"
echo "       python -m ingest.ws_consumer"
echo "       python -m ingest.rest_poller"
echo ""
echo "  2. Wait 2-3 min for data, then run Spark:"
echo "       bash run_spark_jobs.sh"
echo ""
echo "  3. Start API server:"
echo "       uvicorn api.main:app --reload --port 8000"
echo ""
echo "  4. Start dashboard:"
echo "       cd dashboard && npm run dev"
echo ""
echo "  5. Open http://localhost:5173"
echo ""
