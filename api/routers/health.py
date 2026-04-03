"""Health check endpoint."""
from fastapi import APIRouter
from api.services.mongo_client import analytics_db, raw_db

router = APIRouter()


@router.get("/health")
async def health_check():
    try:
        # Check MongoDB connectivity
        raw_count = await raw_db.trades.estimated_document_count()
        enriched_count = await analytics_db.enriched_trades.estimated_document_count()
        metrics_count = await analytics_db.aggregated_metrics.estimated_document_count()

        return {
            "status": "healthy",
            "mongodb": "connected",
            "counts": {
                "raw_trades": raw_count,
                "enriched_trades": enriched_count,
                "aggregated_metrics": metrics_count,
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
        }
