"""GitHub integration routes."""
import uuid
import tempfile
import os
import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List

from app.core.database import get_db, User
from app.core.security import get_current_user
from app.services.github_service import GitHubService

router = APIRouter(prefix="/api/github", tags=["GitHub"])

class GitHubTokenRequest(BaseModel):
    token: str

class CreateRepoRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True

class PushToRepoRequest(BaseModel):
    repo_url: str
    files: List[dict]
    commit_message: str = "Update from PHOENIX Agent"

class PushZipRequest(BaseModel):
    repo_url: str
    commit_message: str = "Update from PHOENIX Agent"

class CreateAndPushRequest(BaseModel):
    name: str
    description: str = ""
    private: bool = True
    commit_message: str = "Initial commit from PHOENIX Agent"

@router.post("/connect")
async def connect_github(
    data: GitHubTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    current_user.github_token = data.token
    gh = GitHubService(current_user)
    is_valid = await gh.validate_token()
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid GitHub token")

    user_info = await gh.get_user_info()
    current_user.github_username = user_info.get("login")
    await db.commit()
    return {"message": "GitHub connected", "username": user_info.get("login")}

@router.get("/repos")
async def get_repos(current_user: User = Depends(get_current_user)):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    gh = GitHubService(current_user)
    repos = await gh.get_user_repos()
    return {"repos": repos}

@router.post("/repos")
async def create_repo(data: CreateRepoRequest, current_user: User = Depends(get_current_user)):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    gh = GitHubService(current_user)
    result = await gh.create_repo(data.name, data.description, data.private)
    return result

@router.post("/push")
async def push_to_repo(data: PushToRepoRequest, current_user: User = Depends(get_current_user)):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")
    gh = GitHubService(current_user)
    parts = data.repo_url.replace("https://github.com/", "").split("/")
    owner = parts[0]
    repo = parts[1].replace(".git", "")
    result = await gh.push_files(owner, repo, data.files, commit_message=data.commit_message)
    return result

@router.post("/push-zip")
async def push_zip_to_repo(
    data: PushZipRequest,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        files = GitHubService.extract_zip(zip_path, temp_dir)
        if not files:
            raise HTTPException(status_code=400, detail="No files found in zip")

        gh = GitHubService(current_user)
        parts = data.repo_url.replace("https://github.com/", "").split("/")
        owner = parts[0]
        repo = parts[1].replace(".git", "")

        result = await gh.push_files(owner, repo, files, commit_message=data.commit_message)

        return {
            "message": f"Successfully pushed {len(files)} files to {data.repo_url}",
            "files_pushed": len(files),
            "commit_sha": result.get("commit_sha")
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@router.post("/create-and-push")
async def create_repo_and_push(
    data: CreateAndPushRequest,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    if not current_user.github_token:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    gh = GitHubService(current_user)
    repo_result = await gh.create_repo(data.name, data.description, data.private)
    repo_url = repo_result["html_url"]
    repo_name = repo_result["name"]

    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, file.filename)

    with open(zip_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        files = GitHubService.extract_zip(zip_path, temp_dir)

        if files:
            user_info = await gh.get_user_info()
            username = user_info.get("login", "")
            await gh.push_files(username, repo_name, files, commit_message=data.commit_message)

        return {
            "repo_url": repo_url,
            "repo_name": repo_name,
            "files_pushed": len(files),
            "message": f"Repository created and {len(files)} files pushed successfully"
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
