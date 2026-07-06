"""Authentication routes."""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr

from app.core.database import get_db, User
from app.core.security import verify_password, get_password_hash, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""

class SignInRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserProfile(BaseModel):
    id: str
    email: str
    full_name: str | None
    use_infrastructure: bool
    github_connected: bool
    created_at: str

@router.post("/signup", response_model=AuthResponse)
async def signup(data: SignUpRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name or None
    )
    db.add(user)
    await db.commit()

    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name}
    )

@router.post("/signin", response_model=AuthResponse)
async def signin(data: SignInRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(data={"sub": user.id})

    return AuthResponse(
        access_token=access_token,
        user={"id": user.id, "email": user.email, "full_name": user.full_name}
    )

@router.get("/me", response_model=UserProfile)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        use_infrastructure=current_user.use_infrastructure if current_user.use_infrastructure is not None else True,
        github_connected=bool(current_user.github_token),
        created_at=str(current_user.created_at)
    )
