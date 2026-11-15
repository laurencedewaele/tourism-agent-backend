"""Sondes de vie et de disponibilité (Docker, orchestrateur)."""
import logging

from fastapi import APIRouter, Request, Response, status

from ..schemas import HealthStatus

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthStatus)
async def health() -> HealthStatus:
    """Le processus répond."""
    return HealthStatus(status="ok")


@router.get("/ready", response_model=HealthStatus)
async def ready(request: Request, response: Response) -> HealthStatus:
    """Le checkpointer est joignable (requête sur PostgreSQL le cas échéant)."""
    pool = getattr(request.app.state, "db_pool", None)
    if pool is None:
        return HealthStatus(status="ok", checkpointer="memory")
    try:
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        logger.exception("PostgreSQL injoignable")
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthStatus(status="unavailable", checkpointer="postgres")
    return HealthStatus(status="ok", checkpointer="postgres")
