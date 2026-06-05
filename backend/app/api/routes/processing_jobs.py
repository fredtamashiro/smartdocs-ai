from fastapi import APIRouter, Depends, HTTPException

from app.api.admin_auth import require_admin_user
from app.services.processing_job_service import get_processing_job, list_processing_jobs


router = APIRouter(
    prefix="/processing-jobs",
    tags=["Processing Jobs"],
)


@router.get("")
def list_jobs(
    _admin_user: dict = Depends(require_admin_user),
):
    jobs = list_processing_jobs()
    return {
        "total": len(jobs),
        "jobs": jobs,
    }


@router.get("/{job_id}")
def get_job(
    job_id: str,
    _admin_user: dict = Depends(require_admin_user),
):
    try:
        return get_processing_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
