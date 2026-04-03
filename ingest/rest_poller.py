"""
REST Poller — periodically fetches option chain snapshots with Greeks/IV/OI
from Polygon/MASSIVE REST API and upserts them into MongoDB.
"""
import time
import logging
import re
from datetime import datetime, timezone

from polygon import RESTClient
from pymongo import MongoClient

from ingest.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

WATCHLIST = ["AAPL", "NVDA", "TSLA", "SPY", "AMZN", "META", "MSFT", "GOOGL", "QQQ", "AMD"]
POLL_INTERVAL = 60  # seconds


def parse_option_symbol(sym: str) -> dict | None:
    m = re.match(r'^O:(\w+?)(\d{6})([CP])(\d{8})$', sym)
    if not m:
        return None
    underlying, date_str, cp, strike_raw = m.groups()
    return {
        'underlying': underlying,
        'expiration': datetime.strptime(date_str, '%y%m%d').strftime('%Y-%m-%d'),
        'contract_type': 'call' if cp == 'C' else 'put',
        'strike': int(strike_raw) / 1000,
    }


def is_market_hours() -> bool:
    """Check if current time is within US market hours (9:30-16:00 ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def snapshot_to_doc(snapshot, underlying: str) -> dict:
    """Convert a Polygon snapshot object to a MongoDB document."""
    details = snapshot.details if hasattr(snapshot, 'details') else None
    greeks = snapshot.greeks if hasattr(snapshot, 'greeks') else None
    last_quote = snapshot.last_quote if hasattr(snapshot, 'last_quote') else None
    last_trade = snapshot.last_trade if hasattr(snapshot, 'last_trade') else None
    day = snapshot.day if hasattr(snapshot, 'day') else None
    underlying_asset = snapshot.underlying_asset if hasattr(snapshot, 'underlying_asset') else None

    doc = {
        "sym": details.ticker if details else None,
        "underlying": underlying,
        "break_even_price": getattr(snapshot, 'break_even_price', None),
        "implied_volatility": getattr(snapshot, 'implied_volatility', None),
        "open_interest": getattr(snapshot, 'open_interest', None),
        "fmv": getattr(snapshot, 'fmv', None),
        "details": {
            "contract_type": getattr(details, 'contract_type', None),
            "exercise_style": getattr(details, 'exercise_style', None),
            "expiration_date": getattr(details, 'expiration_date', None),
            "shares_per_contract": getattr(details, 'shares_per_contract', None),
            "strike_price": getattr(details, 'strike_price', None),
            "ticker": getattr(details, 'ticker', None),
        } if details else {},
        "greeks": {
            "delta": getattr(greeks, 'delta', None),
            "gamma": getattr(greeks, 'gamma', None),
            "theta": getattr(greeks, 'theta', None),
            "vega": getattr(greeks, 'vega', None),
        } if greeks else {},
        "last_quote": {
            "ask": getattr(last_quote, 'ask', None),
            "ask_size": getattr(last_quote, 'ask_size', None),
            "bid": getattr(last_quote, 'bid', None),
            "bid_size": getattr(last_quote, 'bid_size', None),
            "midpoint": getattr(last_quote, 'midpoint', None),
            "timeframe": getattr(last_quote, 'timeframe', None),
            "last_updated": getattr(last_quote, 'last_updated', None),
        } if last_quote else {},
        "last_trade": {
            "price": getattr(last_trade, 'price', None),
            "size": getattr(last_trade, 'size', None),
            "exchange": getattr(last_trade, 'exchange', None),
            "conditions": getattr(last_trade, 'conditions', None),
            "sip_timestamp": getattr(last_trade, 'sip_timestamp', None),
            "timeframe": getattr(last_trade, 'timeframe', None),
        } if last_trade else {},
        "day": {
            "open": getattr(day, 'open', None),
            "high": getattr(day, 'high', None),
            "low": getattr(day, 'low', None),
            "close": getattr(day, 'close', None),
            "volume": getattr(day, 'volume', None),
            "vwap": getattr(day, 'vwap', None),
            "change": getattr(day, 'change', None),
            "change_percent": getattr(day, 'change_percent', None),
            "previous_close": getattr(day, 'previous_close', None),
            "last_updated": getattr(day, 'last_updated', None),
        } if day else {},
        "underlying_asset": {
            "ticker": getattr(underlying_asset, 'ticker', None),
            "price": getattr(underlying_asset, 'price', None),
            "change_to_break_even": getattr(underlying_asset, 'change_to_break_even', None),
            "timeframe": getattr(underlying_asset, 'timeframe', None),
            "last_updated": getattr(underlying_asset, 'last_updated', None),
        } if underlying_asset else {},
        "fetched_at": datetime.now(timezone.utc),
    }

    parsed = parse_option_symbol(doc["sym"]) if doc["sym"] else None
    if parsed:
        doc.update(parsed)

    return doc


def poll_snapshots():
    """Fetch snapshots for all watchlist tickers."""
    rest_client = RESTClient(api_key=settings.POLYGON_API_KEY)
    mongo_client = MongoClient(settings.MONGO_URI)
    db = mongo_client[settings.MONGO_DB]

    logger.info(f"Polling snapshots for {len(WATCHLIST)} tickers...")

    total_inserted = 0
    for ticker in WATCHLIST:
        try:
            docs = []
            for snapshot in rest_client.list_snapshot_options_chain(ticker):
                doc = snapshot_to_doc(snapshot, ticker)
                docs.append(doc)

            if docs:
                db.snapshots.insert_many(docs, ordered=False)
                total_inserted += len(docs)
                logger.info(f"  {ticker}: {len(docs)} contracts")

        except Exception as e:
            logger.error(f"  {ticker}: ERROR — {e}")

    logger.info(f"Poll complete: {total_inserted} total snapshots inserted")
    mongo_client.close()


def main():
    logger.info("Starting REST Poller...")
    logger.info(f"Watchlist: {WATCHLIST}")
    logger.info(f"Poll interval: {POLL_INTERVAL}s")

    while True:
        if is_market_hours():
            try:
                poll_snapshots()
            except Exception as e:
                logger.error(f"Poll cycle failed: {e}")
        else:
            logger.info("Outside market hours — polling anyway for delayed data")
            try:
                poll_snapshots()
            except Exception as e:
                logger.error(f"Poll cycle failed: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
