// === options_raw indexes ===
db = db.getSiblingDB('options_raw');

// trades
db.trades.createIndex({ sym: 1, t: -1 });
db.trades.createIndex({ t: -1 });
db.trades.createIndex({ sym: 1, q: 1 }, { unique: true });

// quotes
db.quotes.createIndex({ sym: 1, t: -1 });
db.quotes.createIndex({ t: -1 });

// aggregates
db.aggregates.createIndex({ sym: 1, s: -1 });

// snapshots
db.snapshots.createIndex({ sym: 1, fetched_at: -1 });
db.snapshots.createIndex({ underlying: 1, fetched_at: -1 });

// === options_analytics indexes ===
db = db.getSiblingDB('options_analytics');

// enriched_trades
db.enriched_trades.createIndex({ underlying: 1, timestamp: -1 });
db.enriched_trades.createIndex({ sector: 1, timestamp: -1 });
db.enriched_trades.createIndex({ unusual_flag: 1, timestamp: -1 });

// aggregated_metrics
db.aggregated_metrics.createIndex({ underlying: 1, date: -1, hour: 1 });
db.aggregated_metrics.createIndex({ sector: 1, date: -1 });

print("=== All indexes created successfully ===");
