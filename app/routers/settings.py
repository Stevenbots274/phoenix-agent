"""User settings routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.core.database import get_db, User
from app.core.security import get_current_user
from app.services.ai_service import AIService

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class UpdateSettingsRequest(BaseModel):
    full_name: Optional[str] = None
    use_infrastructure: Optional[bool] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    preferred_model: Optional[str] = None
    github_token: Optional[str] = None

class SettingsResponse(BaseModel):
    full_name: Optional[str]
    email: str
    use_infrastructure: bool
    openai_api_key_set: bool
    gemini_api_key_set: bool
    preferred_model: Optional[str]
    github_connected: bool

@router.get("/", response_model=SettingsResponse)
async def get_settings(current_user: User = Depends(get_current_user)):
    return SettingsResponse(
        full_name=current_user.full_name,
        email=current_user.email,
        use_infrastructure=current_user.use_infrastructure if current_user.use_infrastructure is not None else True,
        openai_api_key_set=bool(current_user.openai_api_key),
        gemini_api_key_set=bool(current_user.gemini_api_key),
        preferred_model=current_user.preferred_model,
        github_connected=bool(current_user.github_token)
    )

@router.put("/")
async def update_settings(
    data: UpdateSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if data.full_name is not None:
        current_user.full_name = data.full_name
    if data.use_infrastructure is not None:
        current_user.use_infrastructure = data.use_infrastructure
    if data.openai_api_key is not None:
        current_user.openai_api_key = data.openai_api_key if data.openai_api_key else None
    if data.gemini_api_key is not None:
        current_user.gemini_api_key = data.gemini_api_key if data.gemini_api_key else None
    if data.preferred_model is not None:
        current_user.preferred_model = data.preferred_model
    if data.github_token is not None:
        current_user.github_token = data.github_token if data.github_token else None

    await db.commit()
    return {"message": "Settings updated successfully"}

@router.get("/models")
async def get_available_models(current_user: User = Depends(get_current_user)):
    ai = AIService(current_user)
    models = await ai.list_models()
    return {"models": models}
