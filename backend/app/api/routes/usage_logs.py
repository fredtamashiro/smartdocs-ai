from fastapi import APIRouter, Depends

from app.api.admin_auth import require_admin_user
from app.services.usage_log_service import list_usage_logs

router = APIRouter(
    prefix="/usage-logs",
    tags=["Usage Logs"],
)


@router.get("")
def get_usage_logs(
    limit: int = 50,
    _admin_user: dict = Depends(require_admin_user),
):
    logs = list_usage_logs(limit=limit)

    return {
        "total": len(logs),
        "logs": logs,
    }
