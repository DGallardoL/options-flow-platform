"""Query service with the 5 analytical queries + lineage."""
from datetime import datetime
from api.services.mongo_client import analytics_db, raw_db


async def get_flow_scanner(limit: int = 100):
    """Get latest enriched trades for the flow scanner."""
    cursor = analytics_db.enriched_trades.find(
        {}, {"_id": 0}
    ).sort("timestamp", -1).limit(limit)
    return await cursor.to_list(length=limit)


async def get_unusual_activity(date: str | None = None, limit: int = 50):
    """Q1 — Unusual Options Activity: group by sym, sum volume, filter vol/OI > 1.5."""
    match_stage = {"unusual_flag": True}
    if date:
        match_stage["timestamp"] = {"$regex": f"^{date}"}

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$sym",
            "underlying": {"$first": "$underlying"},
            "contract_type": {"$first": "$contract_type"},
            "strike": {"$first": "$strike"},
            "expiration": {"$first": "$expiration"},
            "total_volume": {"$sum": "$size"},
            "total_dollar_volume": {"$sum": "$dollar_volume"},
            "avg_iv": {"$avg": "$implied_volatility"},
            "open_interest": {"$first": "$open_interest"},
            "sentiment": {"$first": "$sentiment"},
            "sector": {"$first": "$sector"},
            "last_price": {"$last": "$price"},
        }},
        {"$addFields": {
            "vol_oi_ratio": {
                "$divide": ["$total_volume", {"$max": ["$open_interest", 1]}]
            }
        }},
        {"$match": {"vol_oi_ratio": {"$gt": 1.5}}},
        {"$sort": {"total_dollar_volume": -1}},
        {"$limit": limit},
    ]
    return await analytics_db.enriched_trades.aggregate(pipeline).to_list(length=limit)


async def get_iv_skew(underlying: str, date: str | None = None):
    """Q2 — IV Skew: bucket delta into P50/P25/P10/C10/C25/C50, avg IV per bucket."""
    match_stage = {"underlying": underlying}
    if date:
        match_stage["timestamp"] = {"$regex": f"^{date}"}

    pipeline = [
        {"$match": match_stage},
        {"$match": {"delta": {"$ne": None}, "implied_volatility": {"$ne": None}}},
        {"$addFields": {
            "delta_bucket": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": ["$delta", -0.40]}, "then": "P50"},
                        {"case": {"$lte": ["$delta", -0.20]}, "then": "P25"},
                        {"case": {"$lte": ["$delta", -0.05]}, "then": "P10"},
                        {"case": {"$lte": ["$delta", 0.05]}, "then": "ATM"},
                        {"case": {"$lte": ["$delta", 0.20]}, "then": "C10"},
                        {"case": {"$lte": ["$delta", 0.40]}, "then": "C25"},
                    ],
                    "default": "C50"
                }
            }
        }},
        {"$group": {
            "_id": "$delta_bucket",
            "avg_iv": {"$avg": "$implied_volatility"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    return await analytics_db.enriched_trades.aggregate(pipeline).to_list(length=20)


async def get_put_call_ratio(date: str | None = None):
    """Q3 — Put/Call Ratio by Sector and Hour."""
    match_stage = {}
    if date:
        match_stage["date"] = date

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": {"sector": "$sector", "hour": "$hour"},
            "total_call_volume": {"$sum": "$total_call_volume"},
            "total_put_volume": {"$sum": "$total_put_volume"},
        }},
        {"$addFields": {
            "put_call_ratio": {
                "$cond": [
                    {"$gt": ["$total_call_volume", 0]},
                    {"$divide": ["$total_put_volume", "$total_call_volume"]},
                    0
                ]
            }
        }},
        {"$sort": {"_id.sector": 1, "_id.hour": 1}},
    ]
    return await analytics_db.aggregated_metrics.aggregate(pipeline).to_list(length=200)


async def get_spread_moneyness(date: str | None = None):
    """Q4 — Spread vs Moneyness: bucket moneyness_pct, avg spread and volume."""
    match_stage = {}
    if date:
        match_stage["timestamp"] = {"$regex": f"^{date}"}

    pipeline = [
        {"$match": match_stage},
        {"$match": {"moneyness_pct": {"$ne": None}, "bid_ask_spread": {"$ne": None}}},
        {"$addFields": {
            "moneyness_bucket": {
                "$switch": {
                    "branches": [
                        {"case": {"$lte": ["$moneyness_pct", -0.15]}, "then": "Deep ITM"},
                        {"case": {"$lte": ["$moneyness_pct", -0.05]}, "then": "ITM"},
                        {"case": {"$lte": ["$moneyness_pct", 0.05]}, "then": "ATM"},
                        {"case": {"$lte": ["$moneyness_pct", 0.15]}, "then": "OTM"},
                    ],
                    "default": "Deep OTM"
                }
            }
        }},
        {"$group": {
            "_id": "$moneyness_bucket",
            "avg_spread": {"$avg": "$bid_ask_spread"},
            "total_volume": {"$sum": "$size"},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    return await analytics_db.enriched_trades.aggregate(pipeline).to_list(length=20)


async def get_gamma_exposure(date: str | None = None, limit: int = 20):
    """Q5 — Gamma Exposure by underlying."""
    match_stage = {}
    if date:
        match_stage["date"] = date

    pipeline = [
        {"$match": match_stage},
        {"$group": {
            "_id": "$underlying",
            "call_gamma": {"$sum": "$call_gamma_exposure"},
            "put_gamma": {"$sum": "$put_gamma_exposure"},
            "net_gamma": {"$sum": "$net_gamma_exposure"},
        }},
        {"$addFields": {
            "call_gamma_m": {"$divide": ["$call_gamma", 1000000]},
            "put_gamma_m": {"$divide": ["$put_gamma", 1000000]},
            "net_gamma_m": {"$divide": ["$net_gamma", 1000000]},
        }},
        {"$sort": {"net_gamma": -1}},
        {"$limit": limit},
    ]
    return await analytics_db.aggregated_metrics.aggregate(pipeline).to_list(length=limit)


async def get_lineage(sym: str):
    """Trace a symbol through all pipeline stages."""
    raw_trade = await raw_db.trades.find_one({"sym": sym}, {"_id": 0})
    cleaned = await analytics_db.cleaned_trades.find_one({"sym": sym}, {"_id": 0})
    enriched = await analytics_db.enriched_trades.find_one({"sym": sym}, {"_id": 0})

    # For aggregated, find by underlying
    underlying = cleaned.get("underlying") if cleaned else None
    aggregated = None
    if underlying:
        aggregated = await analytics_db.aggregated_metrics.find_one(
            {"underlying": underlying}, {"_id": 0}
        )

    return {
        "raw_trade": raw_trade,
        "cleaned_trade": cleaned,
        "enriched_trade": enriched,
        "aggregated_metric": aggregated,
    }
