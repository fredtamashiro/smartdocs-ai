from fastapi import APIRouter, HTTPException

from app.database.database import check_database_connection
from app.services.rate_limit_service import redis_client

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("/database")
def database_healthcheck():
    try:
        return check_database_connection()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar no banco de dados: {error}",
        )


@router.get("/redis")
def redis_healthcheck():
    try:
        redis_client.ping()
        return {"connected": True}
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao conectar no Redis: {error}",
        )
