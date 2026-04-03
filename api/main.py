"""FastAPI backend for Options Flow Intelligence Platform."""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import flow, analytics, health

app = FastAPI(
    title="Options Flow Intelligence API",
    version="1.0.0",
    description="Real-time options flow analytics API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(flow.router, prefix="/api/flow")
app.include_router(analytics.router, prefix="/api/analytics")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
