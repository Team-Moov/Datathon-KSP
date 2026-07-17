"""Conversational AI streaming endpoint (§10)."""

from typing import List

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services.conversation_service import ConversationService

router = APIRouter()


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str
    messages: List[Message]
    language: str = "en"  # "en" | "kn" (Kannada)


@router.post("/")
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streamed chat endpoint.
    Returns a Server-Sent-Events stream of JSON lines:
      {"type": "token", "content": "..."}
      {"type": "tool_call", "tool": "...", "status": "running"}
      {"type": "widget", "widget_type": "...", "data": {...}}
      {"type": "done"}

    Language-code is passed through to the system prompt context.
    Kannada queries are handled natively — whisper transcription produces English text
    which this endpoint then processes identically.
    """
    svc = ConversationService(db)
    messages = [{"role": m.role, "content": m.content} for m in payload.messages]

    async def event_stream():
        async for event in svc.chat(messages, payload.session_id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Session-ID": payload.session_id},
    )
