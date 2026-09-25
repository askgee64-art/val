"""Chat and conversational executive intelligence endpoints — Master Cognitive Loop Integration."""

from __future__ import annotations

from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from val.api.auth import get_current_user
from val.core.cognitive_engine import get_cognitive_engine
from val.db.models import Conversation, Message, User, utcnow
from val.db.session import get_session
from val.models.enums import MessageRole
from val.models.schemas import ChatMessage, ChatResponse, MessageOut, TaskOut

router = APIRouter(prefix="/chat", tags=["Chat & Objectives"])


@router.post("", response_model=ChatResponse)
async def send_chat(
    payload: ChatMessage,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> ChatResponse:
    content = payload.content.strip()

    # 1. Find or create persistent conversation
    conv_id = str(payload.conversation_id) if payload.conversation_id else None
    conv: Conversation | None = None
    if conv_id:
        conv = await session.get(Conversation, conv_id)

    if conv is None:
        title_snippet = content[:36] + ("..." if len(content) > 36 else "")
        conv = Conversation(
            conversation_id=str(uuid4()),
            org_id=user.org_id,
            user_id=user.user_id,
            title=title_snippet,
            status="active",
            created_at=utcnow(),
        )
        session.add(conv)
        await session.flush()

    # 2. Save user message to persistent ledger
    user_msg = Message(
        message_id=str(uuid4()),
        conversation_id=conv.conversation_id,
        org_id=user.org_id,
        role=MessageRole.USER,
        content=content,
        created_at=utcnow(),
    )
    session.add(user_msg)
    await session.flush()

    # 3. Process via Cognitive Engine (Genuine Model Inference, Memory Retrieval, AST Tools)
    cognitive_engine = get_cognitive_engine()
    assistant_text, response_mode, metadata, task, plan = await cognitive_engine.process_interaction(
        session=session,
        user=user,
        conversation=conv,
        content=content,
        auto_execute=payload.auto_execute,
    )

    # 4. Save assistant response to conversation history
    asst_msg = Message(
        message_id=str(uuid4()),
        conversation_id=conv.conversation_id,
        org_id=user.org_id,
        role=MessageRole.ASSISTANT,
        content=assistant_text,
        metadata_json=metadata,
        created_at=utcnow(),
    )
    session.add(asst_msg)
    conv.updated_at = utcnow()
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
        task=TaskOut.model_validate(task) if task else None,
        plan=plan,
        status=task.status.value if task else "succeeded",
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
        .order_by(desc(Conversation.created_at))
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
            role=m.role,
            content=m.content,
            metadata=m.metadata_json,
            created_at=m.created_at,
        )
        for m in res.scalars().all()
    ]
