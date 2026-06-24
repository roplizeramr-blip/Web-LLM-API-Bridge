from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.browser_engine import BrowserEngine
from app.models import ChatCompletionRequest, ChatMessage, ProviderCreateRequest
from app.provider_store import ProviderStore
from app.settings import BASE_DIR, settings


store = ProviderStore()
engine = BrowserEngine(store)
DASHBOARD_PATH = BASE_DIR / "app" / "dashboard.html"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()


app = FastAPI(title="API Bridge", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(DASHBOARD_PATH.read_text(encoding="utf-8"))


@app.get("/api/providers")
async def list_providers() -> dict[str, Any]:
    return {
        "providers": [
            provider.model_dump(mode="json")
            for provider in await engine.list_runtimes()
        ],
        "settings": {
            "port": settings.port,
            "default_model": settings.default_model,
        },
    }


@app.post("/api/providers")
async def add_provider(request: ProviderCreateRequest) -> dict[str, Any]:
    provider = store.upsert(request)
    return {"provider": provider.model_dump(mode="json")}


@app.post("/api/providers/{provider_name}/login")
async def login_provider(provider_name: str) -> dict[str, Any]:
    if not store.exists(provider_name):
        raise HTTPException(status_code=404, detail="Unknown provider")
    runtime = await engine.login(provider_name)
    return {"provider": runtime.model_dump(mode="json")}


@app.get("/v1/models")
async def list_models() -> dict[str, Any]:
    providers = await engine.list_runtimes()
    return {
        "object": "list",
        "data": [
            {
                "id": provider.name,
                "object": "model",
                "created": 0,
                "owned_by": "api-bridge",
                "status": provider.status,
            }
            for provider in providers
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest) -> JSONResponse | StreamingResponse:
    model = request.model or settings.default_model
    if not store.exists(model):
        raise HTTPException(status_code=404, detail=f"Unknown model/provider: {model}")

    prompt = _messages_to_prompt(request.messages)
    if request.stream:
        return StreamingResponse(
            _stream_openai_events(model, prompt),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    content = await engine.complete(model, prompt)
    created = int(time.time())
    return JSONResponse(
        {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        }
    )


async def _stream_openai_events(model: str, prompt: str) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex}"
    created = int(time.time())
    initial = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield _sse(initial)
    try:
        async for chunk in engine.stream(model, prompt):
            if not chunk:
                continue
            payload = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
            }
            yield _sse(payload)
        final = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield _sse(final)
        yield "data: [DONE]\n\n"
    except Exception as exc:  # noqa: BLE001 - stream errors need to reach clients.
        yield _sse({"error": {"message": str(exc), "type": "api_bridge_error"}})
        yield "data: [DONE]\n\n"


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _messages_to_prompt(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for message in messages:
        content = _content_to_text(message.content)
        if not content:
            continue
        if message.role == "user":
            parts.append(content)
        else:
            parts.append(f"{message.role}: {content}")
    return "\n\n".join(parts).strip()


def _content_to_text(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    chunks: list[str] = []
    for item in content:
        if item.get("type") == "text":
            chunks.append(str(item.get("text", "")))
    return "\n".join(chunks)
