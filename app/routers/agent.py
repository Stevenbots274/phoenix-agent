"""Multi-agent task routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.database import get_db, User, AgentTask
from app.core.security import get_current_user
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/agent", tags=["Agent"])

class AgentTaskRequest(BaseModel):
    task_type: str
    input_data: dict

class CodeReviewRequest(BaseModel):
    code: str
    language: str = "python"

class ChatAgentRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: Optional[str] = None

@router.post("/task")
async def create_task(
    data: AgentTaskRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    agent = AgentService(current_user, db)
    task_id = await agent.create_task(data.task_type, data.input_data)
    result = await agent.execute_task(task_id)
    return {"task_id": task_id, "result": result}

@router.get("/tasks")
async def list_tasks(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AgentTask)
        .where(AgentTask.user_id == current_user.id)
        .order_by(AgentTask.created_at.desc())
    )
    tasks = result.scalars().all()
    return [
        {
            "id": t.id,
            "type": t.task_type,
            "status": t.status,
            "created_at": str(t.created_at),
            "completed_at": str(t.completed_at) if t.completed_at else None,
            "error": t.error_message
        } for t in tasks
    ]

@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(AgentTask).where(
            AgentTask.id == task_id,
            AgentTask.user_id == current_user.id
        )
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "id": task.id,
        "type": task.task_type,
        "status": task.status,
        "input": task.input_data,
        "result": task.result_data,
        "error": task.error_message,
        "created_at": str(task.created_at),
        "completed_at": str(task.completed_at) if task.completed_at else None
    }

@router.post("/code-review")
async def code_review(
    data: CodeReviewRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    agent = AgentService(current_user, db)
    result = await agent._handle_code_review({
        "code": data.code,
        "language": data.language
    })
    return result

@router.post("/chat")
async def agent_chat(
    data: ChatAgentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    agent = AgentService(current_user, db)
    result = await agent._handle_chat({
        "messages": data.messages,
        "model": data.model
    })
    return result
