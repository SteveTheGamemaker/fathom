from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@router.get("/scheduler")
async def scheduler_status() -> dict:
    from fathom.scheduler.setup import scheduler

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


@router.post("/scheduler/{job_id}/run")
async def trigger_job(job_id: str) -> dict:
    """Manually trigger a scheduler job to run now."""
    from fathom.scheduler.setup import scheduler

    job = scheduler.get_job(job_id)
    if not job:
        from fastapi import HTTPException
        raise HTTPException(404, f"Job '{job_id}' not found")

    job.modify(next_run_time=None)  # triggers immediate run
    # Actually, APScheduler's way to run now:
    from datetime import datetime, timezone
    job.modify(next_run_time=datetime.now(timezone.utc))
    return {"message": f"Job '{job_id}' triggered"}
