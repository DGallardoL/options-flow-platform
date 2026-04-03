// This script is used as reference — actual user creation is done in setup.sh
// using docker exec with environment variable substitution for passwords.

// Admin (full access)
db.getSiblingDB('admin').createUser({
  user: "admin",
  pwd: "CHANGE_ME_ADMIN",
  roles: [{ role: "root", db: "admin" }]
});

// Ingest Writer (write raw only)
db.getSiblingDB('admin').createUser({
  user: "ingest_writer",
  pwd: "CHANGE_ME_INGEST",
  roles: [{ role: "readWrite", db: "options_raw" }]
});

// Spark Processor (read raw, write analytics)
db.getSiblingDB('admin').createUser({
  user: "spark_processor",
  pwd: "CHANGE_ME_SPARK",
  roles: [
    { role: "read", db: "options_raw" },
    { role: "readWrite", db: "options_analytics" }
  ]
});

// Dashboard Reader (read analytics + raw for lineage/health)
db.getSiblingDB('admin').createUser({
  user: "dashboard_reader",
  pwd: "CHANGE_ME_DASHBOARD",
  roles: [
    { role: "read", db: "options_analytics" },
    { role: "read", db: "options_raw" }
  ]
});
