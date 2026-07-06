"""AI service for multiple providers."""
import httpx
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from app.core.config import get_settings
from app.core.database import User

settings = get_settings()

class AIService:
    def __init__(self, user: User):
        self.user = user

    def _get_active_provider(self) -> str:
        """Determine which AI provider to use."""
        if self.user.use_infrastructure:
            return "infrastructure"
        if self.user.openai_api_key:
            return "openai"
        if self.user.gemini_api_key:
            return "gemini"
        return "infrastructure"  # Fallback

    async def list_models(self) -> List[Dict[str, str]]:
        """List available models based on user settings."""
        provider = self._get_active_provider()
        all_models = []

        if provider == "infrastructure" or self.user.use_infrastructure:
            infra_models = await self._list_infrastructure_models()
            for m in infra_models:
                m["provider"] = "infrastructure"
                all_models.append(m)

        if self.user.openai_api_key:
            openai_models = [
                {"id": "gpt-4o", "name": "GPT-4o", "provider": "openai"},
                {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "openai"},
                {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "provider": "openai"},
            ]
            all_models.extend(openai_models)

        if self.user.gemini_api_key:
            gemini_models = [
                {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "provider": "gemini"},
                {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "provider": "gemini"},
                {"id": "gemini-1.5-flash-8b", "name": "Gemini 1.5 Flash 8B", "provider": "gemini"},
            ]
            all_models.extend(gemini_models)

        return all_models

    async def _list_infrastructure_models(self) -> List[Dict[str, str]]:
        """List models from infrastructure Azure/Ollama."""
        base_url = settings.INFRASTRUCTURE_BASE_URL
        api_key = settings.INFRASTRUCTURE_API_KEY

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
                response = await client.get(
                    f"{base_url.rstrip('/')}/v1/models",
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", data.get("models", []))
                    return [{"id": m.get("id", m.get("name", "unknown")), 
                             "name": m.get("id", m.get("name", "unknown"))} 
                            for m in models]
        except Exception as e:
            print(f"Error listing infrastructure models: {e}")

        return [
            {"id": "tinyllama", "name": "TinyLlama"},
            {"id": "qwen2.5:0.5b", "name": "Qwen 2.5 0.5B"},
        ]

    async def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Send chat completion request."""
        provider = self._get_active_provider()

        # Check if model belongs to a specific provider
        if model:
            if model.startswith("gemini") and self.user.gemini_api_key:
                provider = "gemini"
            elif model in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] and self.user.openai_api_key:
                provider = "openai"
            else:
                provider = "infrastructure"

        if provider == "openai":
            return await self._openai_chat(messages, model, stream, temperature)
        elif provider == "gemini":
            return await self._gemini_chat(messages, model, stream, temperature)
        else:
            return await self._infrastructure_chat(messages, model, stream, temperature)

    async def _infrastructure_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        base_url = settings.INFRASTRUCTURE_BASE_URL
        api_key = settings.INFRASTRUCTURE_API_KEY

        payload = {
            "model": model or "tinyllama",
            "messages": messages,
            "stream": stream,
            "temperature": temperature
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        } if api_key else {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def _openai_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        api_key = self.user.openai_api_key

        payload = {
            "model": model or "gpt-4o-mini",
            "messages": messages,
            "stream": stream,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            response.raise_for_status()
            return response.json()

    async def _gemini_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        api_key = self.user.gemini_api_key
        model_name = model or "gemini-1.5-flash"

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": 8192
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()

            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return {
                "choices": [{
                    "message": {"role": "assistant", "content": text},
                    "finish_reason": "stop"
                }],
                "model": model_name
            }

    async def stream_chat(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        provider = self._get_active_provider()

        if model:
            if model.startswith("gemini") and self.user.gemini_api_key:
                provider = "gemini"
            elif model in ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"] and self.user.openai_api_key:
                provider = "openai"
            else:
                provider = "infrastructure"

        if provider == "openai":
            async for chunk in self._stream_openai(messages, model, temperature):
                yield chunk
        elif provider == "gemini":
            async for chunk in self._stream_gemini(messages, model, temperature):
                yield chunk
        else:
            async for chunk in self._stream_infrastructure(messages, model, temperature):
                yield chunk

    async def _stream_infrastructure(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        base_url = settings.INFRASTRUCTURE_BASE_URL
        api_key = settings.INFRASTRUCTURE_API_KEY

        payload = {
            "model": model or "tinyllama",
            "messages": messages,
            "stream": True,
            "temperature": temperature
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        } if api_key else {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{base_url.rstrip('/')}/v1/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except:
                            pass

    async def _stream_openai(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        api_key = self.user.openai_api_key

        payload = {
            "model": model or "gpt-4o-mini",
            "messages": messages,
            "stream": True,
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                        except:
                            pass

    async def _stream_gemini(
        self, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        api_key = self.user.gemini_api_key
        model_name = model or "gemini-1.5-flash"

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature}
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?alt=sse&key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        text = data["candidates"][0]["content"]["parts"][0].get("text", "")
                        if text:
                            yield text
                    except:
                        pass
