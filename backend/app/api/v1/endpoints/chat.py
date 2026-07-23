"""Conversational AI streaming endpoint (§10)."""

import asyncio
import json
from typing import List

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse, Response
from google.genai import types
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_user_from_token
from app.core.config import settings
from app.core.vertex_ai_client import get_genai_client
from app.models.user import User
from app.services.conversation_service import SYSTEM_PROMPT, ConversationService
from app.services.report_service import build_chat_report_pdf

log = structlog.get_logger(__name__)

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
    svc = ConversationService(db, current_user)
    
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
    Voice Q&A endpoint — one-shot upload-and-transcribe fallback for non-WebSocket
    clients. The real-time duplex voice conversation is the /voice/live WebSocket
    endpoint (Gemini Live). Transcribes via Gemini's native audio understanding
    (replaces Groq Whisper) — Gemini transcribes Kannada natively without a
    separate language-specific model or an explicit language hint.
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty audio upload")

    client = get_genai_client()
    response = await client.aio.models.generate_content(
        model=settings.GEMINI_MODEL_FAST,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=content, mime_type=file.content_type or "audio/webm"),
                    types.Part(text="Transcribe this audio verbatim, in its original language (English or Kannada). Return only the transcription, no commentary."),
                ],
            )
        ],
    )
    return {"text": response.text}


@router.websocket("/voice/live")
async def chat_voice_live(
    websocket: WebSocket,
    token: str = Query(...),
    language: str = Query("en"),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time duplex voice conversation via Gemini Live.

    Browser clients can't attach a normal Authorization header to a WebSocket
    handshake, so the JWT travels as a query param and is validated manually
    via get_user_from_token — the exact same validation get_current_user uses
    for REST routes, just not reachable through the oauth2_scheme Depends here.

    Wire protocol once connected:
      - Binary frames FROM the client → raw PCM16 mono 16kHz audio chunks (mic input)
      - Binary frames TO the client   → raw audio chunks from Gemini (playback)
      - Text frames TO the client     → JSON control events, the same vocabulary
        as the REST /chat/ stream: {"type": "token"|"tool_call"|"tool_result"|"widget"|"error"|"done", ...}

    Shares its tool surface with the text chat path (ConversationService's
    dispatch table + widget mapping) rather than duplicating it, so a voice
    query can reach the same deterministic tools a typed query can.
    """
    try:
        current_user = await get_user_from_token(token, db)
    except HTTPException:
        await websocket.close(code=4401)
        return

    await websocket.accept()

    svc = ConversationService(db, current_user)
    client = get_genai_client()

    system_instruction = SYSTEM_PROMPT
    if language == "kn":
        system_instruction += (
            "\n\nYou MUST reply to the investigator entirely in Kannada language (kn). Do NOT reply in English."
        )

    live_config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=system_instruction,
        tools=svc._gemini_tools,
    )

    async def relay_client_audio_to_gemini(session) -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            audio_bytes = message.get("bytes")
            if audio_bytes:
                await session.send_realtime_input(
                    audio=types.Blob(data=audio_bytes, mime_type="audio/pcm;rate=16000")
                )

    async def relay_gemini_to_client(session) -> None:
        async for response in session.receive():
            if response.data:
                await websocket.send_bytes(response.data)
            if response.text:
                await websocket.send_text(json.dumps({"type": "token", "content": response.text}))

            tool_call = getattr(response, "tool_call", None)
            if tool_call and tool_call.function_calls:
                function_responses = []
                for fc in tool_call.function_calls:
                    await websocket.send_text(json.dumps({"type": "tool_call", "tool": fc.name, "status": "running"}))
                    result = await svc._dispatch_tool(fc.name, dict(fc.args or {}))
                    widget_event = svc._map_to_widget(fc.name, result)
                    if widget_event:
                        await websocket.send_text(json.dumps({"type": "widget", **widget_event}, default=str))
                    await websocket.send_text(json.dumps({"type": "tool_result", "tool": fc.name, "data": result}, default=str))
                    function_responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result}))
                await session.send_tool_response(function_responses=function_responses)

            server_content = getattr(response, "server_content", None)
            if server_content and getattr(server_content, "turn_complete", False):
                await websocket.send_text(json.dumps({"type": "done"}))

    try:
        async with client.aio.live.connect(model=settings.GEMINI_LIVE_MODEL, config=live_config) as session:
            await asyncio.gather(
                relay_client_audio_to_gemini(session),
                relay_gemini_to_client(session),
            )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        log.error("Gemini Live session failed", error=str(exc))
        try:
            await websocket.send_text(json.dumps({
                "type": "error",
                "error": "ai_unavailable",
                "message": "Voice assistance is temporarily unavailable. Please retry shortly.",
            }))
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


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
