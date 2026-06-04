"""Background task tracking (TZ section 7 note: long-running operations).

Some operations — OCR-ing a large scan, parsing a big PDF — take time. Rather
than block the HTTP request, the API can create a *task*, return its id
immediately, and let the client poll ``GET /api/v1/task/{id}``. This service is
the single place that creates and mutates those task rows.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database.models import Task, TaskStatus
from app.utils.logger import get_logger

log = get_logger("udip.tasks")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_task(db: Session, *, task_type: str, document_id: int | None = None) -> Task:
    task = Task(type=task_type, status=TaskStatus.PENDING, progress=0, document_id=document_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    log.info("Task %s created (type=%s)", task.id, task_type)
    return task


def start_task(db: Session, task_id: str) -> None:
    task = db.get(Task, task_id)
    if task:
        task.status = TaskStatus.RUNNING
        task.started_at = _utcnow()
        task.progress = max(task.progress, 1)
        db.commit()


def update_progress(db: Session, task_id: str, progress: int) -> None:
    task = db.get(Task, task_id)
    if task:
        task.progress = max(0, min(100, progress))
        db.commit()


def complete_task(db: Session, task_id: str, result: dict | None = None) -> None:
    task = db.get(Task, task_id)
    if task:
        task.status = TaskStatus.SUCCESS
        task.progress = 100
        task.result = result
        task.finished_at = _utcnow()
        db.commit()
        log.info("Task %s completed", task_id)


def fail_task(db: Session, task_id: str, error: str) -> None:
    task = db.get(Task, task_id)
    if task:
        task.status = TaskStatus.FAILED
        task.error = error[:4000]
        task.finished_at = _utcnow()
        db.commit()
        log.warning("Task %s failed: %s", task_id, error)


def get_task(db: Session, task_id: str) -> Task | None:
    return db.get(Task, task_id)
