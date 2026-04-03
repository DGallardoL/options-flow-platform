"""
WebSocket Consumer — connects to Polygon/MASSIVE options WebSocket,
buffers events and flushes to MongoDB in batches.
"""
import signal
import sys
import time
import logging
from datetime import datetime, timezone
from threading import Timer

from polygon import WebSocketClient
from pymongo import MongoClient, errors as mongo_errors

from ingest.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# --- Buffers ---
trade_buffer: list[dict] = []
quote_buffer: list[dict] = []
agg_buffer: list[dict] = []

# --- Counters ---
counts = {"trades": 0, "quotes": 0, "aggs": 0}
last_log_time = time.time()

# --- MongoDB ---
mongo_client = MongoClient(settings.MONGO_URI)
db = mongo_client[settings.MONGO_DB]


def flush_buffers():
    """Flush all buffers to MongoDB."""
    global trade_buffer, quote_buffer, agg_buffer

    now = datetime.now(timezone.utc)

    if trade_buffer:
        batch = trade_buffer.copy()
        trade_buffer.clear()
        for doc in batch:
            doc["_ingested_at"] = now
        try:
            db.trades.insert_many(batch, ordered=False)
        except mongo_errors.BulkWriteError as e:
            n_inserted = e.details.get("nInserted", 0)
            logger.warning(f"Trades bulk write: {n_inserted} inserted, some duplicates skipped")

    if quote_buffer:
        batch = quote_buffer.copy()
        quote_buffer.clear()
        for doc in batch:
            doc["_ingested_at"] = now
        try:
            db.quotes.insert_many(batch, ordered=False)
        except mongo_errors.BulkWriteError:
            pass

    if agg_buffer:
        batch = agg_buffer.copy()
        agg_buffer.clear()
        for doc in batch:
            doc["_ingested_at"] = now
        try:
            db.aggregates.insert_many(batch, ordered=False)
        except mongo_errors.BulkWriteError:
            pass


def log_stats():
    """Log events/minute."""
    global last_log_time, counts
    elapsed = time.time() - last_log_time
    if elapsed >= 60:
        logger.info(
            f"Events/min — Trades: {counts['trades']}, "
            f"Quotes: {counts['quotes']}, Aggs: {counts['aggs']}"
        )
        counts = {"trades": 0, "quotes": 0, "aggs": 0}
        last_log_time = time.time()


def trade_to_dict(m) -> dict:
    return {
        "ev": "T",
        "sym": m.symbol,
        "x": getattr(m, "exchange", None),
        "p": m.price,
        "s": m.size,
        "c": getattr(m, "conditions", None),
        "t": m.timestamp,
        "q": m.sequence_number,
    }


def quote_to_dict(m) -> dict:
    return {
        "ev": "Q",
        "sym": m.symbol,
        "bx": getattr(m, "bid_exchange", None),
        "ax": getattr(m, "ask_exchange", None),
        "bp": m.bid_price,
        "ap": m.ask_price,
        "bs": m.bid_size,
        "as": m.ask_size,
        "t": m.timestamp,
        "q": m.sequence_number,
    }


def agg_to_dict(m) -> dict:
    return {
        "ev": "A",
        "sym": m.symbol,
        "v": m.volume,
        "av": getattr(m, "accumulated_volume", None),
        "op": getattr(m, "official_open_price", None),
        "vw": m.vwap,
        "o": m.open,
        "c": m.close,
        "h": m.high,
        "l": m.low,
        "a": getattr(m, "aggregate_vwap", None),
        "z": getattr(m, "average_size", None),
        "s": m.start_timestamp,
        "e": m.end_timestamp,
    }


def handle_msg(msgs):
    """Handle incoming WebSocket messages."""
    for m in msgs:
        ev_type = m.event_type

        if ev_type == "T":
            trade_buffer.append(trade_to_dict(m))
            counts["trades"] += 1
        elif ev_type == "Q":
            quote_buffer.append(quote_to_dict(m))
            counts["quotes"] += 1
        elif ev_type == "A":
            agg_buffer.append(agg_to_dict(m))
            counts["aggs"] += 1

        total = len(trade_buffer) + len(quote_buffer) + len(agg_buffer)
        if total >= settings.FLUSH_SIZE:
            flush_buffers()

    log_stats()


def periodic_flush():
    """Periodically flush buffers."""
    flush_buffers()
    timer = Timer(settings.FLUSH_INTERVAL, periodic_flush)
    timer.daemon = True
    timer.start()


def shutdown(signum, frame):
    """Graceful shutdown."""
    logger.info("Shutting down — flushing remaining buffers...")
    flush_buffers()
    mongo_client.close()
    logger.info("Shutdown complete.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info("Starting Options WebSocket Consumer...")
    logger.info(f"Connecting to MongoDB: {settings.MONGO_DB}")

    periodic_flush()

    ws = WebSocketClient(
        api_key=settings.POLYGON_API_KEY,
        market="options",
        subscriptions=["T.*", "Q.*", "A.*"],
    )

    logger.info("WebSocket connected — listening for T.*, Q.*, A.*")
    ws.run(handle_msg=handle_msg)


if __name__ == "__main__":
    main()
