"""
server.py — KIRA Phase 1: Laptop-side AI Server

This is the brain of KIRA. It runs on your laptop and does three things:
1. Receives audio recordings from the phone
2. Transcribes audio to text using OpenAI Whisper (runs locally, NOT the API)
3. Sends the text to phi3:mini via Ollama and returns the AI response

Endpoints:
  POST /voice   — accepts audio file, transcribes + generates response
  POST /chat    — accepts raw text, generates response (for testing)
  GET  /health  — connectivity check for the phone client

Requirements: FastAPI, uvicorn, whisper, httpx, python-multipart
"""

import os
import tempfile
import logging
from datetime import datetime

import httpx
import whisper
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")  # tiny | base | small

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
    description="Phase 1 — Voice pipeline server for KIRA personal assistant",
    version="0.1.0",
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
log.info(f"Loading Whisper model '{WHISPER_MODEL_SIZE}' ...")
whisper_model = whisper.load_model(WHISPER_MODEL_SIZE)
log.info("Whisper model loaded ✓")


# ---------------------------------------------------------------------------
# Ollama helper — sends a prompt to phi3:mini and streams the full response
# ---------------------------------------------------------------------------
async def query_ollama(prompt: str, conversation_history: list[dict] | None = None) -> str:
    """
    Send a prompt to Ollama's /api/chat endpoint and return the full response.
    Uses the chat API so we can pass conversation history later (Phase 2).
    """
    messages = []

    # System prompt — gives KIRA its personality
    messages.append({
        "role": "system",
        "content": (
            "You are KIRA, a personal AI assistant. "
            "You are helpful, concise, and conversational. "
            "Keep responses short and natural — you're being spoken aloud. "
            "Avoid bullet points and markdown formatting since your output "
            "will be converted to speech. Speak like a smart friend, not a textbook."
        ),
    })

    # Append any conversation history if provided
    if conversation_history:
        messages.extend(conversation_history)

    # Append the current user message
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,  # get the full response at once
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
    Transcribe audio file using local Whisper model.
    Supports WAV, MP3, M4A, FLAC, OGG, and more.
    """
    log.info(f"Transcribing: {audio_path}")
    result = whisper_model.transcribe(audio_path, fp16=False)
    text = result["text"].strip()
    log.info(f"Transcribed: '{text}'")
    return text


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for the /chat text endpoint."""
    message: str


class KiraResponse(BaseModel):
    """Standard response from KIRA."""
    transcription: str | None = None  # only set when audio was sent
    response: str
    model: str = OLLAMA_MODEL
    timestamp: str


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
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/chat", response_model=KiraResponse)
async def chat_text(req: ChatRequest):
    """
    Text-based chat endpoint — useful for testing without voice.
    Send a JSON body: {"message": "your question here"}
    """
    log.info(f"[/chat] Received: '{req.message}'")
    response_text = await query_ollama(req.message)
    log.info(f"[/chat] Response: '{response_text[:80]}...'")

    return KiraResponse(
        response=response_text,
        timestamp=datetime.now().isoformat(),
    )


@app.post("/voice", response_model=KiraResponse)
async def voice_chat(audio: UploadFile = File(...)):
    """
    Voice chat endpoint — the main Phase 1 pipeline:
    1. Receive audio file from phone
    2. Transcribe to text with Whisper
    3. Send text to phi3:mini via Ollama
    4. Return the AI response as text (phone handles TTS)
    """
    log.info(f"[/voice] Received audio: {audio.filename} ({audio.content_type})")

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
            )

        # Step 2: Get AI response from phi3:mini
        response_text = await query_ollama(transcription)
        log.info(f"[/voice] Response: '{response_text[:80]}...'")

        return KiraResponse(
            transcription=transcription,
            response=response_text,
            timestamp=datetime.now().isoformat(),
        )
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    log.info("=" * 50)
    log.info("  KIRA Server — Phase 1 Voice Pipeline")
    log.info(f"  Model: {OLLAMA_MODEL}")
    log.info(f"  Whisper: {WHISPER_MODEL_SIZE}")
    log.info(f"  Ollama: {OLLAMA_BASE_URL}")
    log.info("=" * 50)

    uvicorn.run(app, host="0.0.0.0", port=8000)
