"""Multi-agent orchestration service."""
import uuid
from typing import List, Dict, Any, Optional
from app.services.ai_service import AIService
from app.services.github_service import GitHubService
from app.core.database import User, AgentTask
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class AgentService:
    def __init__(self, user: User, db: AsyncSession):
        self.user = user
        self.db = db
        self.ai = AIService(user)
        self.github = GitHubService(user)

    async def create_task(self, task_type: str, input_data: dict) -> str:
        task = AgentTask(
            id=str(uuid.uuid4()),
            user_id=self.user.id,
            task_type=task_type,
            input_data=input_data,
            status="pending"
        )
        self.db.add(task)
        await self.db.commit()
        return task.id

    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        result = await self.db.execute(
            select(AgentTask).where(AgentTask.id == task_id)
        )
        task = result.scalar_one_or_none()
        if not task:
            return {"error": "Task not found"}

        task.status = "running"
        await self.db.commit()

        try:
            if task.task_type == "github_push":
                result_data = await self._handle_github_push(task.input_data)
            elif task.task_type == "github_create_repo":
                result_data = await self._handle_create_repo(task.input_data)
            elif task.task_type == "github_create_and_push":
                result_data = await self._handle_create_and_push(task.input_data)
            elif task.task_type == "file_analysis":
                result_data = await self._handle_file_analysis(task.input_data)
            elif task.task_type == "code_review":
                result_data = await self._handle_code_review(task.input_data)
            elif task.task_type == "chat":
                result_data = await self._handle_chat(task.input_data)
            else:
                result_data = await self._handle_generic(task.input_data)

            task.status = "completed"
            task.result_data = result_data
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            result_data = {"error": str(e)}

        await self.db.commit()
        return result_data

    async def _handle_github_push(self, data: dict) -> dict:
        repo_url = data.get("repo_url")
        files = data.get("files", [])
        commit_message = data.get("commit_message", "Update from PHOENIX Agent")

        parts = repo_url.replace("https://github.com/", "").split("/")
        owner = parts[0]
        repo = parts[1].replace(".git", "")

        result = await self.github.push_files(
            owner, repo, files,
            commit_message=commit_message
        )
        return result

    async def _handle_create_repo(self, data: dict) -> dict:
        name = data.get("name")
        description = data.get("description", "")
        private = data.get("private", True)

        result = await self.github.create_repo(name, description, private)
        return {
            "repo_url": result.get("html_url"),
            "clone_url": result.get("clone_url"),
            "repo_name": result.get("name")
        }

    async def _handle_create_and_push(self, data: dict) -> dict:
        """Create repo + push files in one task."""
        name = data.get("name")
        description = data.get("description", "")
        private = data.get("private", True)
        files = data.get("files", [])

        # Create repo
        repo_result = await self.github.create_repo(name, description, private)
        repo_name = repo_result["name"]

        # Get username
        user_info = await self.github.get_user_info()
        username = user_info.get("login", "")

        # Push files
        if files:
            await self.github.push_files(
                username, repo_name, files,
                commit_message="Initial commit from PHOENIX Agent"
            )

        return {
            "repo_url": repo_result.get("html_url"),
            "repo_name": repo_name,
            "files_pushed": len(files),
            "message": f"Repository created and {len(files)} files pushed successfully"
        }

    async def _handle_file_analysis(self, data: dict) -> dict:
        files = data.get("files", [])
        question = data.get("question", "Analyze these files and provide insights.")

        context = ""
        for f in files:
            if not f.get("is_binary", False):
                context += f"\n\n--- {f['path']} ---\n{f['content'][:5000]}"

        messages = [
            {"role": "system", "content": "You are PHOENIX Agent, a multi-agent AI assistant. Analyze the provided files and answer the user's question."},
            {"role": "user", "content": f"Files:\n{context}\n\nQuestion: {question}"}
        ]

        response = await self.ai.chat_completion(messages)
        content = response["choices"][0]["message"]["content"]

        return {"analysis": content, "files_analyzed": len(files)}

    async def _handle_code_review(self, data: dict) -> dict:
        code = data.get("code", "")
        language = data.get("language", "python")

        messages = [
            {"role": "system", "content": f"You are a senior {language} developer. Review the code for bugs, security issues, performance, and best practices."},
            {"role": "user", "content": f"Review this {language} code:\n\n```{language}\n{code}\n```"}
        ]

        response = await self.ai.chat_completion(messages)
        content = response["choices"][0]["message"]["content"]

        return {"review": content}

    async def _handle_chat(self, data: dict) -> dict:
        messages = data.get("messages", [])
        model = data.get("model")

        response = await self.ai.chat_completion(messages, model=model)
        return response

    async def _handle_generic(self, data: dict) -> dict:
        prompt = data.get("prompt", "")

        messages = [
            {"role": "system", "content": "You are PHOENIX Agent, a multi-agent AI assistant. Help the user with their request."},
            {"role": "user", "content": prompt}
        ]

        response = await self.ai.chat_completion(messages)
        return response
