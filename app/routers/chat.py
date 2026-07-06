"""Chat and conversation routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db, ChatSession, ChatMessage, User
from app.core.security import get_current_user
from app.services.ai_service import AIService

router = APIRouter(prefix="/api/chat", tags=["Chat"])

class ChatMessageRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    model: Optional[str] = None
    stream: bool = False

class ChatSessionResponse(BaseModel):
    id: str
    title: str
    model: str
    created_at: str
    updated_at: str

class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    model_used: Optional[str]
    created_at: str

@router.get("/sessions", response_model=List[ChatSessionResponse])
async def get_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(desc(ChatSession.updated_at))
    )
    sessions = result.scalars().all()
    return [
        ChatSessionResponse(
            id=s.id,
            title=s.title or "New Chat",
            model=s.model or "infrastructure",
            created_at=str(s.created_at),
            updated_at=str(s.updated_at)
        ) for s in sessions
    ]

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        ChatMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            model_used=m.model_used,
            created_at=str(m.created_at)
        ) for m in messages
    ]

@router.post("/send")
async def send_message(
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if data.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == data.session_id,
                ChatSession.user_id == current_user.id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    else:
        session = ChatSession(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=data.message[:50],
            model=current_user.preferred_model or "infrastructure"
        )
        db.add(session)
        await db.commit()

    user_msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session.id,
        role="user",
        content=data.message
    )
    db.add(user_msg)
    await db.commit()

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history = result.scalars().all()

    messages = [
        {"role": "system", "content": "You are PHOENIX Agent, a multi-agent AI assistant. You can help with coding, file analysis, GitHub operations, and general questions. If the user asks to create a repo and push files, help them do that."}
    ]
    for h in history[-20:]:
        messages.append({"role": h.role, "content": h.content})

    ai = AIService(current_user)

    if data.stream:
        async def stream_response():
            full_response = ""
            async for chunk in ai.stream_chat(messages, model=data.model):
                full_response += chunk
                yield f"data: {chunk}\n\n"

            assistant_msg = ChatMessage(
                id=str(uuid.uuid4()),
                session_id=session.id,
                role="assistant",
                content=full_response,
                model_used=data.model or session.model
            )
            db.add(assistant_msg)
            await db.commit()
            yield "data: [DONE]\n\n"

        return StreamingResponse(stream_response(), media_type="text/event-stream")
    else:
        response = await ai.chat_completion(messages, model=data.model)
        content = response["choices"][0]["message"]["content"]

        assistant_msg = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session.id,
            role="assistant",
            content=content,
            model_used=data.model or session.model
        )
        db.add(assistant_msg)
        await db.commit()

        return {
            "session_id": session.id,
            "message": content,
            "model_used": data.model or session.model
        }

@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
    await db.commit()
    return {"message": "Session deleted"}
