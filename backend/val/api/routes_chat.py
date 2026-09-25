"""Chat and objective intake endpoints — Document 30 §3 & Document 22 §3."""

from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.core.orchestrator import get_orchestrator
from val.db.models import Conversation, Message, Task, User, utcnow
from val.db.session import get_session
from val.models.enums import MessageRole, TaskStatus
from val.models.schemas import ChatMessage, ChatResponse, MessageOut, TaskOut

router = APIRouter(prefix="/chat", tags=["Chat & Objectives"])


@router.post("", response_model=ChatResponse)
async def send_chat(
    payload: ChatMessage,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    orchestrator = get_orchestrator()

    # Find or create conversation
    conv_id = str(payload.conversation_id) if payload.conversation_id else None
    conv: Conversation | None = None
    if conv_id:
        conv = await session.get(Conversation, conv_id)

    if conv is None:
        conv = Conversation(
            conversation_id=str(uuid4()),
            org_id=user.org_id,
            user_id=user.user_id,
            title=f"Objective: {payload.content[:40]}...",
            status="active",
            created_at=utcnow(),
        )
        session.add(conv)
        await session.flush()

    # Save user message
    user_msg = Message(
        message_id=str(uuid4()),
        conversation_id=conv.conversation_id,
        org_id=user.org_id,
        role=MessageRole.USER,
        content=payload.content,
        created_at=utcnow(),
    )
    session.add(user_msg)
    await session.flush()

    # Pass objective into Orchestrator Autonomy Loop
    task, plan = await orchestrator.submit_objective(
        session,
        objective=payload.content,
        user_id=user.user_id,
        org_id=user.org_id,
        auto_execute=payload.auto_execute,
    )

    # Format assistant response summarizing plan and status
    assistant_text = f"**VAL Executive Plan**: {plan.summary}\n\n"
    assistant_text += f"Steps ({len(plan.steps)}):\n"
    for s in plan.steps:
        icon = "✅" if s.status == "succeeded" else ("⏳" if s.status == "waiting_approval" else "🔹")
        tool_tag = f" `[{s.tool_name}]`" if s.tool_name else ""
        assistant_text += f"{icon} **Step {s.step_id}**: {s.title}{tool_tag} — *{s.status}*\n"

    if task.status == TaskStatus.WAITING_APPROVAL:
        assistant_text += "\n⚠️ **Approval Required**: Step requires Level 4 founder authorization. Review in Approvals."
    elif task.status == TaskStatus.SUCCEEDED:
        assistant_text += "\n🎯 **Objective completed successfully.**"
    elif task.status == TaskStatus.FAILED:
        assistant_text += f"\n❌ **Task halted**: {task.error}"

    asst_msg = Message(
        message_id=str(uuid4()),
        conversation_id=conv.conversation_id,
        org_id=user.org_id,
        role=MessageRole.ASSISTANT,
        content=assistant_text,
        metadata_json={
            "task_id": task.task_id,
            "plan_id": plan.plan_id,
            "status": task.status,
        },
        created_at=utcnow(),
    )
    session.add(asst_msg)
    await session.commit()

    return ChatResponse(
        conversation_id=conv.conversation_id,
        message=MessageOut(
            message_id=asst_msg.message_id,
            conversation_id=asst_msg.conversation_id,
            role=MessageRole.ASSISTANT,
            content=asst_msg.content,
            metadata=asst_msg.metadata_json,
            created_at=asst_msg.created_at,
        ),
        task=TaskOut.model_validate(task),
        plan=plan,
        status=task.status,
    )


@router.get("/conversations")
async def list_conversations(
    limit: int = 20,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[dict]:
    q = (
        select(Conversation)
        .where(Conversation.org_id == user.org_id)
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    res = await session.execute(q)
    return [
        {
            "conversation_id": c.conversation_id,
            "title": c.title,
            "status": c.status,
            "created_at": c.created_at.isoformat(),
        }
        for c in res.scalars().all()
    ]


@router.get("/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conv_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[MessageOut]:
    conv = await session.get(Conversation, conv_id)
    if conv is None or conv.org_id != user.org_id:
        raise HTTPException(status_code=404, detail="conversation_not_found")

    q = (
        select(Message)
        .where(Message.conversation_id == conv_id)
        .order_by(Message.created_at.asc())
    )
    res = await session.execute(q)
    return [
        MessageOut(
            message_id=m.message_id,
            conversation_id=m.conversation_id,
            role=MessageRole(m.role),
            content=m.content,
            metadata=m.metadata_json,
            created_at=m.created_at,
        )
        for m in res.scalars().all()
    ]
