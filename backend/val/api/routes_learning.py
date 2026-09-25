"""Learning System & Founder Teaching API endpoints — Prompt Spec §14, §15."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from learning.engine import get_learning_engine
from learning.founder_teaching import get_founder_teaching_service
from learning.models import FounderTeachingInput, LearningObjectiveCreate
from val.api.auth import get_current_user
from val.db.models import KnowledgeItem, User
from val.db.session import get_session

router = APIRouter(prefix="/learning", tags=["Learning & Founder Teaching"])


@router.post("/objectives")
async def create_learning_objective(
    body: LearningObjectiveCreate,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    engine = get_learning_engine()
    state = await engine.initialize_objective(
        session,
        org_id=user.org_id,
        user_id=user.user_id,
        data=body,
    )
    await session.commit()
    return state


@router.get("/objectives")
async def list_learning_objectives(
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    engine = get_learning_engine()
    return engine.list_objectives(user.org_id)


@router.get("/objectives/{objective_id}")
async def get_learning_objective(
    objective_id: str,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    engine = get_learning_engine()
    state = engine.get_objective_state(objective_id)
    if not state:
        raise HTTPException(status_code=404, detail="learning_objective_not_found")
    return state


@router.post("/objectives/{objective_id}/advance")
async def advance_learning_step(
    objective_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    engine = get_learning_engine()
    try:
        res = await engine.advance_learning(session, objective_id)
        await session.commit()
        return {
            "topic_title": res.topic_title,
            "practice_score": res.practice_score,
            "weakness_identified": res.weakness_identified,
            "next_action": res.next_action,
            "overall_progress": res.overall_progress,
            "teaching_readiness": res.teaching_readiness,
        }
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/teach")
async def founder_teach_val(
    body: FounderTeachingInput,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Founder personally teaches VAL company directives, standards, or principles."""
    if user.role != "founder":
        raise HTTPException(status_code=403, detail="founder_teaching_is_restricted_to_founder")

    teaching_svc = get_founder_teaching_service()
    result = await teaching_svc.teach(
        session,
        statement=body.statement,
        org_id=user.org_id,
        founder_user_id=user.user_id,
        domain_or_topic=body.domain_or_topic,
        scope=body.scope,
    )
    await session.commit()
    return {
        "knowledge_id": result.knowledge_id,
        "classified_topic": result.classified_topic,
        "scope": result.scope,
        "stored_statement": result.stored_statement,
        "clarifying_questions": result.clarifying_questions,
        "provenance": result.provenance,
    }


@router.get("/teachings")
async def list_founder_teachings(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict[str, Any]]:
    q = (
        select(KnowledgeItem)
        .where(
            KnowledgeItem.org_id == user.org_id,
            KnowledgeItem.source_type == "founder_teaching",
        )
        .order_by(desc(KnowledgeItem.created_at))
        .limit(limit)
    )
    res = await session.execute(q)
    return [
        {
            "knowledge_id": k.knowledge_id,
            "title": k.title,
            "content": k.content,
            "source_type": k.source_type,
            "provenance": k.provenance,
            "quality_score": k.quality_score,
            "created_at": k.created_at.isoformat() if k.created_at else None,
        }
        for k in res.scalars().all()
    ]
