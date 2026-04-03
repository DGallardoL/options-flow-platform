"""Flow scanner endpoints."""
from fastapi import APIRouter, Query
from api.services.query_service import get_flow_scanner, get_unusual_activity

router = APIRouter()


@router.get("/scanner")
async def flow_scanner(limit: int = Query(100, le=500)):
    data = await get_flow_scanner(limit)
    return {"data": data, "count": len(data)}


@router.get("/unusual")
async def unusual_flow(
    date: str | None = Query(None),
    limit: int = Query(50, le=200),
):
    data = await get_unusual_activity(date, limit)
    return {"data": data, "count": len(data)}
