"""Conversational AI streaming endpoint (§10)."""

from typing import List
import tempfile
import os

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from groq import AsyncGroq

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.config import settings
from app.models.user import User
from app.services.conversation_service import ConversationService
from app.services.report_service import build_chat_report_pdf

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
    """
    svc = ConversationService(db)
    
    # Real Kannada support: Instruct LLM to reply in Kannada if selected
    if payload.language == "kn":
        sys_prompt = "You MUST reply to the investigator entirely in Kannada language (kn). Do NOT reply in English."
        messages = [{"role": "system", "content": sys_prompt}]
    else:
        messages = []
        
    messages.extend([{"role": m.role, "content": m.content} for m in payload.messages])

    async def event_stream():
        async for event in svc.chat(messages, payload.session_id):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"X-Session-ID": payload.session_id},
    )


@router.post("/voice")
async def chat_voice(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Voice Q&A endpoint. Transcribes audio using Groq Whisper.
    """
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Groq API key not configured")
        
    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = await client.audio.transcriptions.create(
                file=(file.filename, audio_file.read()),
                model=getattr(settings, "GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
            )
    finally:
        os.remove(tmp_path)
        
    return {"text": transcription.text}


@router.post("/export")
async def export_chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export conversation history to PDF.
    """
    messages_dicts = [{"role": m.role, "content": m.content} for m in payload.messages]
    pdf_bytes = await build_chat_report_pdf(
        messages=messages_dicts,
        session_id=payload.session_id,
        issued_to=current_user
    )
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=chat_{payload.session_id}.pdf"
        }
    )
