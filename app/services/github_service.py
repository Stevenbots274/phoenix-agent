"""GitHub integration service."""
import os
import tempfile
import zipfile
import base64
from typing import Optional, List, Dict, Any
from pathlib import Path
import httpx
from app.core.database import User

class GitHubService:
    def __init__(self, user: User):
        self.user = user
        self.token = user.github_token
        self.api_base = "https://api.github.com"

    def _headers(self) -> dict:
        return {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "PHOENIX-Agent"
        }

    async def validate_token(self) -> bool:
        if not self.token:
            return False
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/user",
                headers=self._headers()
            )
            return response.status_code == 200

    async def get_user_info(self) -> Dict[str, Any]:
        if not self.token:
            return {}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/user",
                headers=self._headers()
            )
            if response.status_code == 200:
                return response.json()
            return {}

    async def get_user_repos(self) -> List[Dict[str, Any]]:
        if not self.token:
            return []
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_base}/user/repos?sort=updated&per_page=100",
                headers=self._headers()
            )
            if response.status_code == 200:
                return response.json()
            return []

    async def create_repo(
        self, 
        name: str, 
        description: str = "", 
        private: bool = True,
        auto_init: bool = False
    ) -> Dict[str, Any]:
        payload = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/user/repos",
                json=payload,
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()

    async def push_files(
        self, 
        repo_owner: str, 
        repo_name: str, 
        files: List[Dict[str, str]],
        branch: str = "main",
        commit_message: str = "Update from PHOENIX Agent"
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            # Get reference
            ref_resp = await client.get(
                f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}",
                headers=self._headers()
            )

            if ref_resp.status_code == 404:
                repo_resp = await client.get(
                    f"{self.api_base}/repos/{repo_owner}/{repo_name}",
                    headers=self._headers()
                )
                repo_data = repo_resp.json()
                default_branch = repo_data.get("default_branch", "main")

                ref_resp = await client.get(
                    f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/refs/heads/{default_branch}",
                    headers=self._headers()
                )
                base_sha = ref_resp.json()["object"]["sha"]

                await client.post(
                    f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/refs",
                    json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                    headers=self._headers()
                )

                ref_resp = await client.get(
                    f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}",
                    headers=self._headers()
                )

            latest_commit_sha = ref_resp.json()["object"]["sha"]

            # Get tree
            commit_resp = await client.get(
                f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/commits/{latest_commit_sha}",
                headers=self._headers()
            )
            base_tree_sha = commit_resp.json()["tree"]["sha"]

            # Create blobs
            tree_items = []
            for file_info in files:
                content = file_info["content"]
                if isinstance(content, str):
                    content = content.encode("utf-8")

                blob_resp = await client.post(
                    f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/blobs",
                    json={
                        "content": base64.b64encode(content).decode("utf-8"),
                        "encoding": "base64"
                    },
                    headers=self._headers()
                )
                blob_sha = blob_resp.json()["sha"]

                tree_items.append({
                    "path": file_info["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha
                })

            # Create new tree
            tree_resp = await client.post(
                f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/trees",
                json={"base_tree": base_tree_sha, "tree": tree_items},
                headers=self._headers()
            )
            new_tree_sha = tree_resp.json()["sha"]

            # Create commit
            commit_resp = await client.post(
                f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/commits",
                json={
                    "message": commit_message,
                    "tree": new_tree_sha,
                    "parents": [latest_commit_sha]
                },
                headers=self._headers()
            )
            new_commit_sha = commit_resp.json()["sha"]

            # Update reference
            await client.patch(
                f"{self.api_base}/repos/{repo_owner}/{repo_name}/git/refs/heads/{branch}",
                json={"sha": new_commit_sha, "force": False},
                headers=self._headers()
            )

            return {
                "commit_sha": new_commit_sha,
                "tree_sha": new_tree_sha,
                "files_pushed": len(files)
            }

    @staticmethod
    def extract_zip(zip_path: str, extract_to: str) -> List[Dict[str, str]]:
        files = []
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.endswith('/'):
                    continue
                try:
                    content = zf.read(name)
                    try:
                        text_content = content.decode('utf-8')
                        files.append({"path": name, "content": text_content, "is_binary": False})
                    except UnicodeDecodeError:
                        files.append({"path": name, "content": content, "is_binary": True})
                except Exception:
                    continue
        return files

    @staticmethod
    def read_directory_files(directory: str, base_path: str = "") -> List[Dict[str, str]]:
        files = []
        dir_path = Path(directory)
        for item in dir_path.rglob("*"):
            if item.is_file():
                relative_path = str(item.relative_to(dir_path))
                if base_path:
                    relative_path = f"{base_path}/{relative_path}"
                try:
                    with open(item, 'rb') as f:
                        content = f.read()
                    try:
                        text = content.decode('utf-8')
                        files.append({"path": relative_path, "content": text, "is_binary": False})
                    except:
                        files.append({"path": relative_path, "content": content, "is_binary": True})
                except:
                    continue
        return files
