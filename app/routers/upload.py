"""File upload and analysis routes."""
import uuid
import os
import tempfile
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db, User, UploadedFile
from app.core.security import get_current_user
from app.services.github_service import GitHubService
from app.services.agent_service import AgentService

router = APIRouter(prefix="/api/upload", tags=["Upload"])

UPLOAD_DIR = "/app/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class AnalyzeRequest(BaseModel):
    file_id: str
    question: str = "Analyze this file and provide insights."

@router.post("/")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    file_id = str(uuid.uuid4())
    stored_name = f"{file_id}_{file.filename}"
    stored_path = os.path.join(UPLOAD_DIR, stored_name)

    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)

    extracted = None
    try:
        if file.content_type and file.content_type.startswith("text/"):
            extracted = content.decode("utf-8", errors="ignore")
        elif file.filename.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".md", ".txt", ".yaml", ".yml", ".xml", ".sql")):
            extracted = content.decode("utf-8", errors="ignore")
    except:
        pass

    uploaded = UploadedFile(
        id=file_id,
        user_id=current_user.id,
        original_name=file.filename,
        stored_path=stored_path,
        file_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        extracted_content=extracted
    )
    db.add(uploaded)
    await db.commit()

    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "type": file.content_type,
        "extracted_preview": extracted[:500] if extracted else None
    }

@router.get("/")
async def list_uploads(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UploadedFile).where(UploadedFile.user_id == current_user.id)
        .order_by(UploadedFile.created_at.desc())
    )
    files = result.scalars().all()
    return [
        {
            "id": f.id,
            "filename": f.original_name,
            "type": f.file_type,
            "size": f.file_size,
            "has_extracted": f.extracted_content is not None,
            "created_at": str(f.created_at)
        } for f in files
    ]

@router.post("/analyze")
async def analyze_file(
    data: AnalyzeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == data.file_id,
            UploadedFile.user_id == current_user.id
        )
    )
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    files_to_analyze = []
    if file_record.original_name.endswith(".zip"):
        temp_dir = tempfile.mkdtemp()
        try:
            import zipfile
            with zipfile.ZipFile(file_record.stored_path, 'r') as zf:
                zf.extractall(temp_dir)
            files_to_analyze = GitHubService.read_directory_files(temp_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    elif file_record.extracted_content:
        files_to_analyze = [{
            "path": file_record.original_name,
            "content": file_record.extracted_content,
            "is_binary": False
        }]
    else:
        raise HTTPException(status_code=400, detail="Cannot analyze this file type")

    agent = AgentService(current_user, db)
    result = await agent._handle_file_analysis({
        "files": files_to_analyze,
        "question": data.question
    })

    return result

@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(UploadedFile).where(
            UploadedFile.id == file_id,
            UploadedFile.user_id == current_user.id
        )
    )
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")

    if os.path.exists(file_record.stored_path):
        os.remove(file_record.stored_path)

    await db.delete(file_record)
    await db.commit()
    return {"message": "File deleted"}
