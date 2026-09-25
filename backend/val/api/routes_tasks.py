"""Tasks endpoints — Document 21 §4.5 & Master Spec §4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.db.models import Task, User, utcnow
from val.db.session import get_session
from val.models.enums import TaskStatus
from val.models.schemas import TaskOut

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    status: str | None = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[TaskOut]:
    q = select(Task).where(Task.org_id == user.org_id)
    if status:
        q = q.where(Task.status == status)
    q = q.order_by(desc(Task.created_at)).limit(limit)

    res = await session.execute(q)
    return [TaskOut.model_validate(t) for t in res.scalars().all()]


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = await session.get(Task, task_id)
    if task is None or task.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="task_not_found")
    return TaskOut.model_validate(task)


@router.post("/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(
    task_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> TaskOut:
    task = await session.get(Task, task_id)
    if task is None or task.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="task_not_found")

    if task.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"cannot cancel task in state {task.status}")

    task.status = TaskStatus.CANCELLED
    task.completed_at = utcnow()
    await session.commit()
    return TaskOut.model_validate(task)
