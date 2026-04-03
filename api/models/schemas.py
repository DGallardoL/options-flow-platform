"""Pydantic schemas for API responses."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    mongodb: str | None = None
    error: str | None = None


class TradeDoc(BaseModel):
    sym: str | None = None
    underlying: str | None = None
    contract_type: str | None = None
    strike: float | None = None
    price: float | None = None
    size: int | None = None
    dollar_volume: float | None = None
    implied_volatility: float | None = None
    sentiment: str | None = None
    unusual_flag: bool | None = None
    sector: str | None = None
    timestamp: str | None = None
