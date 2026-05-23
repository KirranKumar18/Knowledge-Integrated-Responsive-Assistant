"""
server.py — KIRA Phase 2: Laptop-side AI Server

This is the brain of KIRA. It runs on your laptop and handles:
1. Receives audio recordings from the phone
2. Transcribes audio to text using OpenAI Whisper (runs locally, NOT the API)
3. Sends the text to phi3:mini via Ollama and returns the AI response
4. [Phase 2] Maintains conversation history per session
5. [Phase 2] Detects weak responses and suggests Gemini fallback
6. [Phase 2] Provides a /gemini endpoint for user-approved Gemini queries

Endpoints:
  POST /voice                — accepts audio file, transcribes + generates response
  POST /chat                 — accepts raw text, generates response (for testing)
  POST /gemini               — user-approved Gemini query (permission gate)
  GET  /health               — connectivity check for the phone client
  GET  /sessions/{id}        — view conversation history for a session
  DELETE /sessions/{id}      — clear a session's history

Requirements: FastAPI, uvicorn, whisper, httpx, python-multipart, google-genai
"""

import os
import tempfile
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Load .env file — so API keys persist without manual env var setup
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

import httpx
from faster_whisper import WhisperModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from gemini_handler import needs_gemini, query_gemini, is_gemini_available

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "large-v3-turbo")  # large-v3-turbo = best accuracy/speed ratio

# Phase 2: Session settings
MAX_HISTORY_MESSAGES = 10  # keep last 10 messages (5 user + 5 assistant) per session

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kira-server")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="KIRA Server",
    description="Phase 2 — Voice pipeline with memory and Gemini fallback",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Load Whisper model at startup (one-time, cached in memory)
# ---------------------------------------------------------------------------
log.info(f"Loading faster-whisper model '{WHISPER_MODEL_SIZE}' ...")
try:
    whisper_model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device="cpu",             # CPU mode — works on all systems
        compute_type="int8",      # quantized for speed + lower memory
    )
except Exception as e:
    log.warning(f"int8 failed ({e}), trying float32...")
    whisper_model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device="cpu",
        compute_type="float32",
    )
log.info("faster-whisper model loaded ✓")

# ---------------------------------------------------------------------------
# Phase 2: Session-based conversation memory
# ---------------------------------------------------------------------------
# In-memory store: {session_id: [{"role": "user", "content": "..."}, ...]}
# Each session tracks the conversation so KIRA remembers what you said earlier.
# Trimmed to MAX_HISTORY_MESSAGES to stay within phi3:mini's 4K context window.
sessions: dict[str, list[dict]] = {}


def get_session_history(session_id: str | None) -> list[dict]:
    """Get conversation history for a session. Returns empty list if no session."""
    if not session_id:
        return []
    return sessions.get(session_id, [])


def update_session(session_id: str | None, user_message: str, assistant_response: str):
    """
    Append a user-assistant exchange to the session history.
    Trims to MAX_HISTORY_MESSAGES to prevent context overflow.
    """
    if not session_id:
        return

    if session_id not in sessions:
        sessions[session_id] = []
        log.info(f"New session created: {session_id[:8]}...")

    sessions[session_id].append({"role": "user", "content": user_message})
    sessions[session_id].append({"role": "assistant", "content": assistant_response})

    # Trim: keep only the last N messages
    if len(sessions[session_id]) > MAX_HISTORY_MESSAGES:
        sessions[session_id] = sessions[session_id][-MAX_HISTORY_MESSAGES:]
        log.info(f"Session {session_id[:8]}... trimmed to {MAX_HISTORY_MESSAGES} messages")


# ---------------------------------------------------------------------------
# Ollama helper — sends a prompt to phi3:mini and streams the full response
# ---------------------------------------------------------------------------
async def query_ollama(prompt: str, conversation_history: list[dict] | None = None) -> str:
    """
    Send a prompt to Ollama's /api/chat endpoint and return the full response.
    Uses the chat API with conversation history for multi-turn context.
    """
    messages = []

    # System prompt — gives KIRA its personality
    messages.append({
        "role": "system",
        "content": (
            "You are KIRA, a personal AI voice assistant. "
            "Rules you must follow strictly:\n"
            "1. Keep every reply to 1-2 sentences maximum. Never write paragraphs.\n"
            "2. No bullet points, no lists, no markdown — plain spoken English only.\n"
            "3. Be casual and friendly, like a smart friend texting you.\n"
            "4. If asked how you are or small talk, reply in ONE short sentence.\n"
            "5. Your output is spoken aloud — shorter is always better."
        ),
    })

    # Append conversation history from session (Phase 2)
    if conversation_history:
        messages.extend(conversation_history)

    # Append the current user message
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,  # get the full response at once
        "options": {
            "num_predict": 80,   # hard cap: ~60 words max — keeps responses short and fast
            "temperature": 0.7,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
    except httpx.ConnectError:
        log.error("Cannot connect to Ollama — is it running?")
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Start it with: ollama serve",
        )
    except Exception as e:
        log.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")


# ---------------------------------------------------------------------------
# Whisper helper — transcribe an audio file to text
# ---------------------------------------------------------------------------
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio file using faster-whisper (CTranslate2 backend).
    Optimized for low-latency voice assistant use (short utterances).
    """
    log.info(f"Transcribing: {audio_path}")
    segments, info = whisper_model.transcribe(
        audio_path,
        language="en",                      # skip language detection (~7s saved)
        beam_size=1,                        # greedy decoding — fastest for short audio
        vad_filter=True,                    # Silero VAD — skips silence
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
        condition_on_previous_text=False,   # prevents context buildup slowdown
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    log.info(f"Transcribed ({info.language}, {info.language_probability:.0%}): '{text}'")
    return text


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for the /chat text endpoint."""
    message: str
    session_id: Optional[str] = None  # Phase 2: session tracking


class GeminiRequest(BaseModel):
    """Request body for the /gemini endpoint — user-approved Gemini query."""
    prompt: str
    session_id: Optional[str] = None


class KiraResponse(BaseModel):
    """Standard response from KIRA."""
    transcription: Optional[str] = None  # only set when audio was sent
    response: str
    model: str = OLLAMA_MODEL
    timestamp: str
    session_id: Optional[str] = None       # Phase 2: echo back the session ID
    gemini_suggested: bool = False          # Phase 2: True if Gemini fallback is recommended


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """
    Health check endpoint. The phone client pings this first to verify
    connectivity before sending any voice data.
    """
    # Also check if Ollama is reachable
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "online",
        "ollama": "connected" if ollama_ok else "disconnected",
        "model": OLLAMA_MODEL,
        "whisper_model": WHISPER_MODEL_SIZE,
        "gemini_available": is_gemini_available(),  # Phase 2
        "active_sessions": len(sessions),            # Phase 2
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/chat", response_model=KiraResponse)
async def chat_text(req: ChatRequest):
    """
    Text-based chat endpoint — useful for testing without voice.
    Send a JSON body: {"message": "your question here", "session_id": "optional-uuid"}
    """
    log.info(f"[/chat] Received: '{req.message}' (session: {req.session_id or 'none'})")

    # Get conversation history for this session
    history = get_session_history(req.session_id)

    # Query phi3:mini with history context
    response_text = await query_ollama(req.message, conversation_history=history)
    log.info(f"[/chat] Response: '{response_text[:80]}...'")

    # Phase 2: Check if Gemini should be suggested
    suggest_gemini = needs_gemini(response_text)

    # Save this exchange to session history
    update_session(req.session_id, req.message, response_text)

    return KiraResponse(
        response=response_text,
        timestamp=datetime.now().isoformat(),
        session_id=req.session_id,
        gemini_suggested=suggest_gemini,
    )


@app.post("/voice", response_model=KiraResponse)
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: Optional[str] = Form(None),  # Phase 2: session ID sent as form field
):
    """
    Voice chat endpoint — the main pipeline:
    1. Receive audio file from phone
    2. Transcribe to text with Whisper
    3. Send text to phi3:mini via Ollama (with conversation history)
    4. Return the AI response as text (phone handles TTS)
    5. [Phase 2] Flag if Gemini fallback is suggested
    """
    log.info(f"[/voice] Received audio: {audio.filename} ({audio.content_type}) (session: {session_id or 'none'})")

    # Save uploaded audio to a temp file for Whisper
    suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe audio → text
        transcription = transcribe_audio(tmp_path)

        if not transcription:
            return KiraResponse(
                transcription="",
                response="I didn't catch that. Could you say it again?",
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
            )

        # Step 2: Get conversation history for context
        history = get_session_history(session_id)

        # Step 3: Get AI response from phi3:mini with history
        response_text = await query_ollama(transcription, conversation_history=history)
        log.info(f"[/voice] Response: '{response_text[:80]}...'")

        # Step 4: Check if Gemini should be suggested
        suggest_gemini = needs_gemini(response_text)

        # Step 5: Save this exchange to session history
        update_session(session_id, transcription, response_text)

        return KiraResponse(
            transcription=transcription,
            response=response_text,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            gemini_suggested=suggest_gemini,
        )
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@app.post("/gemini", response_model=KiraResponse)
async def gemini_query(req: GeminiRequest):
    """
    Phase 2: Gemini fallback endpoint — called ONLY after user grants permission.

    The flow:
    1. /chat or /voice returns gemini_suggested=true
    2. Client asks user: "Should I use Gemini for this?"
    3. User says yes → client calls this endpoint
    4. This endpoint sends the prompt to Gemini and returns the upgraded response
    """
    log.info(f"[/gemini] User approved Gemini for: '{req.prompt[:60]}...' (session: {req.session_id or 'none'})")

    if not is_gemini_available():
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable.",
        )

    # Get conversation history for context
    history = get_session_history(req.session_id)

    # Query Gemini
    gemini_response = await query_gemini(req.prompt, conversation_history=history)

    if gemini_response is None:
        raise HTTPException(
            status_code=500,
            detail="Gemini query failed. Check server logs for details.",
        )

    # Update session with the Gemini response (replaces the weak phi3 response)
    # We pop the last assistant message and replace it with Gemini's
    if req.session_id and req.session_id in sessions:
        session = sessions[req.session_id]
        # Remove the last assistant message (the weak phi3 response)
        if session and session[-1]["role"] == "assistant":
            session.pop()
            session.append({"role": "assistant", "content": gemini_response})

    return KiraResponse(
        response=gemini_response,
        model=f"gemini ({os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')})",
        timestamp=datetime.now().isoformat(),
        session_id=req.session_id,
        gemini_suggested=False,
    )


# ---------------------------------------------------------------------------
# Phase 2: Session management endpoints
# ---------------------------------------------------------------------------

@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """View the conversation history for a specific session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": session_id,
        "message_count": len(sessions[session_id]),
        "messages": sessions[session_id],
    }


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Clear a session's conversation history.
    Use when the user says "forget this conversation" or "new conversation".
    """
    if session_id in sessions:
        del sessions[session_id]
        log.info(f"Session {session_id[:8]}... deleted")
        return {"status": "deleted", "session_id": session_id}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    log.info("=" * 50)
    log.info("  KIRA Server — Phase 2: Connect the Brain")
    log.info(f"  Model: {OLLAMA_MODEL}")
    log.info(f"  Whisper: {WHISPER_MODEL_SIZE}")
    log.info(f"  Ollama: {OLLAMA_BASE_URL}")
    log.info(f"  Gemini: {'available' if is_gemini_available() else 'not configured'}")
    log.info(f"  History: last {MAX_HISTORY_MESSAGES} messages per session")
    log.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000)
