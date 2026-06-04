"""Task status endpoint (TZ section 7: GET /api/v1/task/{id})."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.task import TaskOut
from app.services import task_service

router = APIRouter(prefix="/task", tags=["task"])


@router.get("/{task_id}", response_model=TaskOut, summary="Vazifa holatini tekshirish")
def get_task(task_id: str, db: Session = Depends(get_db)) -> TaskOut:
    """Return the status/progress/result of a background task."""
    task = task_service.get_task(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Vazifa topilmadi")
    return TaskOut.model_validate(task)
