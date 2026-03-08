"""Tasks router — weekly checklist item management and report task assignments."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.shift_report import ShiftReport
from models.weekly_task import ReportTaskAssignment, WeeklyTask
from schemas.task import (
    TaskAssignmentOut,
    TaskCheckToggle,
    TaskCreate,
    TaskListResponse,
    TaskOut,
    TaskUpdate,
)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(include_inactive: bool = False, db: Session = Depends(get_db)):
    """List all weekly tasks."""
    query = db.query(WeeklyTask)
    if not include_inactive:
        query = query.filter(WeeklyTask.is_active.is_(True))
    tasks = query.order_by(WeeklyTask.sort_order, WeeklyTask.id).all()
    return TaskListResponse(tasks=tasks)


@router.post("", response_model=TaskOut, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    """Create a new weekly task."""
    task = WeeklyTask(**data.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    """Update a weekly task."""
    task = db.query(WeeklyTask).filter(WeeklyTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(task, key, value)

    db.commit()
    db.refresh(task)
    return task


# ── Report-level task assignments ──────────────────────────

report_tasks_router = APIRouter(prefix="/api/reports", tags=["Tasks"])


@report_tasks_router.get("/{report_id}/tasks")
def list_report_tasks(report_id: int, db: Session = Depends(get_db)):
    """List task assignments for a report, auto-creating missing assignments."""
    report = db.query(ShiftReport).filter(ShiftReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    active_tasks = (
        db.query(WeeklyTask)
        .filter(WeeklyTask.is_active.is_(True))
        .order_by(WeeklyTask.sort_order, WeeklyTask.id)
        .all()
    )

    # Ensure assignments exist for all active tasks
    existing = {
        a.task_id: a
        for a in db.query(ReportTaskAssignment)
        .filter(ReportTaskAssignment.report_id == report_id)
        .all()
    }

    new_added = False
    for task in active_tasks:
        if task.id not in existing:
            assignment = ReportTaskAssignment(
                report_id=report_id, task_id=task.id, is_checked=False,
            )
            db.add(assignment)
            existing[task.id] = assignment
            new_added = True

    if new_added:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Reload existing assignments after race condition
            existing = {
                a.task_id: a
                for a in db.query(ReportTaskAssignment)
                .filter(ReportTaskAssignment.report_id == report_id)
                .all()
            }

    result = []
    for task in active_tasks:
        a = existing.get(task.id)
        if a is None:
            continue
        result.append(
            TaskAssignmentOut(
                task_id=task.id,
                task_title=task.title,
                is_checked=a.is_checked or False,
                checked_by=a.checked_by,
                checked_at=a.checked_at,
            )
        )

    return {"assignments": result}


@report_tasks_router.patch("/{report_id}/tasks/{task_id}", response_model=TaskAssignmentOut)
def toggle_report_task(
    report_id: int,
    task_id: int,
    data: TaskCheckToggle,
    db: Session = Depends(get_db),
):
    """Toggle a task's checked state for a specific report."""
    assignment = (
        db.query(ReportTaskAssignment)
        .filter(
            ReportTaskAssignment.report_id == report_id,
            ReportTaskAssignment.task_id == task_id,
        )
        .first()
    )
    if not assignment:
        # Auto-create if not exists
        report = db.query(ShiftReport).filter(ShiftReport.id == report_id).first()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        task = db.query(WeeklyTask).filter(WeeklyTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        assignment = ReportTaskAssignment(report_id=report_id, task_id=task_id)
        db.add(assignment)

    assignment.is_checked = data.is_checked
    assignment.checked_by = data.checked_by
    assignment.checked_at = datetime.now(timezone.utc).replace(tzinfo=None) if data.is_checked else None

    db.commit()
    db.refresh(assignment)

    task = db.query(WeeklyTask).filter(WeeklyTask.id == task_id).first()
    return TaskAssignmentOut(
        task_id=task_id,
        task_title=task.title if task else "",
        is_checked=assignment.is_checked,
        checked_by=assignment.checked_by,
        checked_at=assignment.checked_at,
    )
