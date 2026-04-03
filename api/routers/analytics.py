"""Analytics endpoints — the 5 analytical queries + lineage."""
from fastapi import APIRouter, Query
from api.services.query_service import (
    get_iv_skew,
    get_put_call_ratio,
    get_spread_moneyness,
    get_gamma_exposure,
    get_lineage,
)

router = APIRouter()


@router.get("/iv-skew")
async def iv_skew(
    underlying: str = Query("AAPL"),
    date: str | None = Query(None),
):
    data = await get_iv_skew(underlying, date)
    return {"data": data, "underlying": underlying}


@router.get("/put-call-ratio")
async def put_call_ratio(date: str | None = Query(None)):
    data = await get_put_call_ratio(date)
    return {"data": data}


@router.get("/spread-moneyness")
async def spread_moneyness(date: str | None = Query(None)):
    data = await get_spread_moneyness(date)
    return {"data": data}


@router.get("/gamma-exposure")
async def gamma_exposure(
    date: str | None = Query(None),
    limit: int = Query(20, le=50),
):
    data = await get_gamma_exposure(date, limit)
    return {"data": data}


@router.get("/lineage")
async def lineage(sym: str = Query(...)):
    data = await get_lineage(sym)
    return {"data": data}
