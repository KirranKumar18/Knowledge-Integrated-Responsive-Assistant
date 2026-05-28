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
import re
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Load .env file — so API keys persist without manual env var setup
# ---------------------------------------------------------------------------
_env_path = Path(__file__).parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

import httpx

# ---------------------------------------------------------------------------
# Programmatic CUDA & cuDNN DLL configuration for Windows (faster-whisper GPU compatibility)
# ---------------------------------------------------------------------------
if os.name == "nt":
    # CTranslate2 / faster-whisper on Windows looks for cublas64_12.dll and cudnn DLLs.
    # If the user has a different CUDA Toolkit version (like CUDA 13) or missing cuDNN,
    # we can dynamically load them from PyPI's nvidia packages if they are installed.
    try:
        import nvidia.cublas
        import nvidia.cudnn
        cublas_bin = Path(list(nvidia.cublas.__path__)[0]) / "bin"
        cudnn_bin = Path(list(nvidia.cudnn.__path__)[0]) / "bin"
        
        if cublas_bin.exists():
            os.add_dll_directory(str(cublas_bin))
            print(f"Added nvidia-cublas DLL directory to search path: {cublas_bin}")
        if cudnn_bin.exists():
            os.add_dll_directory(str(cudnn_bin))
            print(f"Added nvidia-cudnn DLL directory to search path: {cudnn_bin}")
    except Exception as e:
        print(f"Could not load custom nvidia DLL paths: {e}")

from faster_whisper import WhisperModel
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from handlers.gemini_handler import needs_gemini, query_gemini, is_gemini_available
from handlers.calendar_handler import get_schedule, add_reminder
from handlers.task_reminder import add_task, get_pending_reminders, mark_done, list_tasks, get_task_count
from services import monitor, load_monitor
from fastapi.responses import HTMLResponse, FileResponse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "phi3:mini")
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "large-v3-turbo")  # large-v3-turbo = best accuracy/speed ratio

# Phase 2: Session settings
MAX_HISTORY_MESSAGES = 4  # 2 user + 2 assistant turns — keeps phi3:mini's 4K context window safe

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("kira-server")

# Suppress spammy endpoints from uvicorn access logs
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return "/api/stats" not in message and "/alerts" not in message

logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor.start()
    yield
    monitor.stop()
    load_monitor.stop()

app = FastAPI(
    title="KIRA Server",
    description="Phase 3 — Voice pipeline, Gemini fallback, and Productivity tracking",
    version="0.3.0",
    lifespan=lifespan,
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
    log.info("Attempting to load Whisper model on CUDA (GPU)...")
    whisper_model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device="cuda",
        compute_type="float16",  # float16 is standard & fastest for CUDA
    )
    log.info("faster-whisper model loaded on GPU (CUDA) ✓")
except Exception as gpu_err:
    log.warning(f"Failed to load Whisper on GPU ({gpu_err}). Falling back to CPU...")
    try:
        whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",      # quantized for speed + lower memory
        )
        log.info("faster-whisper model loaded on CPU (int8) ✓")
    except Exception as e:
        log.warning(f"int8 failed ({e}), trying float32 on CPU...")
        whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="float32",
        )
        log.info("faster-whisper model loaded on CPU (float32) ✓")

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

    # If conversation_history is None, we are running the first pass (Intent/Tool detection)
    # where we want phi3:mini to follow strict tool-calling formatting without being biased by conversational history.
    if conversation_history is None:
        # Phase 1: Tool-calling system prompt
        now = datetime.now()
        from datetime import timedelta
        today_date_str = now.strftime("%Y-%m-%d")
        today_day_str = now.strftime("%A")
        tomorrow_date_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        june_2_date_str = f"{now.year}-06-02"
        
        days_to_friday = (4 - now.weekday()) % 7
        if days_to_friday == 0:
            days_to_friday = 7
        friday_date_str = (now + timedelta(days=days_to_friday)).strftime("%Y-%m-%d")
        
        current_date_str = now.strftime("%Y-%m-%d, %A")
        system_content = (
            "You are KIRA, a personal AI voice assistant.\n"
            f"Today's date is {current_date_str}.\n\n"
            "You have access to these tools. When the user's request needs one, "
            "respond ONLY with the TOOL and ARGS block, and nothing else (no comments, notes, or extra text).\n"
            "Important: Keep task summaries and event names specific and exact. Do not generalize them (e.g., do not change 'buy milk' to 'Buy milk').\n\n"
            "TOOL: add_reminder\n"
            "ARGS: {\"summary\": \"event name\", \"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\", \"duration_minutes\": 60}\n\n"
            "TOOL: get_schedule\n"
            "ARGS: {\"date\": \"YYYY-MM-DD\", \"query\": \"event name\"}\n\n"
            "TOOL: add_task\n"
            "ARGS: {\"summary\": \"task name\"}\n\n"
            "TOOL: mark_done\n"
            "ARGS: {\"keyword\": \"task name\"}\n\n"
            "TOOL: list_tasks\n"
            "ARGS: {\"keyword\": \"task name\"}\n\n"
            "Rules for resolving dates:\n"
            "1. To schedule a reminder, resolve relative dates (like 'tomorrow', 'next Tuesday') or absolute dates (like '2nd of june') to the actual target date in YYYY-MM-DD format based on today's date.\n"
            "2. For keyword schedule searches (e.g., 'when is my X event', 'when do I have X'), do NOT include the 'date' argument unless a specific day is explicitly mentioned by the user.\n\n"
            "If no tool is needed, respond normally in plain conversational text.\n"
            "Rules for normal responses:\n"
            "1. Keep every reply to 1-2 sentences maximum. Never write paragraphs.\n"
            "2. No bullet points, no lists, no markdown — plain spoken English only.\n"
            "3. Be casual and friendly. No fillers.\n\n"
            f"Examples (assume today is {today_day_str}, {today_date_str}):\n"
            f"- \"remind me about standup tomorrow at 9\" -> TOOL: add_reminder\nARGS: {{\"summary\": \"Standup\", \"date\": \"{tomorrow_date_str}\", \"time\": \"09:00\", \"duration_minutes\": 60}}\n"
            f"- \"test on 2nd of june at 3pm\" -> TOOL: add_reminder\nARGS: {{\"summary\": \"Test\", \"date\": \"{june_2_date_str}\", \"time\": \"15:00\", \"duration_minutes\": 60}}\n"
            "- \"what's on my calendar\" -> TOOL: get_schedule\nARGS: {}\n"
            "- \"when do I have test scheduled on\" -> TOOL: get_schedule\nARGS: {\"query\": \"test\"}\n"
            "- \"when is my gym event scheduled\" -> TOOL: get_schedule\nARGS: {\"query\": \"gym\"}\n"
            f"- \"what is my schedule today\" -> TOOL: get_schedule\nARGS: {{\"date\": \"{today_date_str}\"}}\n"
            f"- \"what is my schedule tomorrow\" -> TOOL: get_schedule\nARGS: {{\"date\": \"{tomorrow_date_str}\"}}\n"
            f"- \"do i have anything on Friday\" -> TOOL: get_schedule\nARGS: {{\"date\": \"{friday_date_str}\"}}\n"
            "- \"I need to buy milk\" -> TOOL: add_task\nARGS: {\"summary\": \"Buy milk\"}\n"
            "- \"finished buying milk\" -> TOOL: mark_done\nARGS: {\"keyword\": \"buy milk\"}\n"
            "- \"what are my tasks\" -> TOOL: list_tasks\nARGS: {}\n"
            "- \"when do I have task buy milk scheduled\" -> TOOL: list_tasks\nARGS: {\"keyword\": \"buy milk\"}\n"
            "- \"when is my homework task scheduled\" -> TOOL: list_tasks\nARGS: {\"keyword\": \"homework\"}\n"
            "- \"what is python\" -> Python is a high-level programming language."
        )
    else:
        # Phase 2: Simple conversational-only system prompt (no tools)
        system_content = (
            "You are KIRA, a personal AI voice assistant. "
            "Rules you must follow strictly:\n"
            "1. Keep every reply to 1-2 sentences maximum. Never write paragraphs.\n"
            "2. No bullet points, no lists, no markdown — plain spoken English only.\n"
            "3. Be casual and friendly, like a smart friend texting you.\n"
            "4. If asked how you are or small talk, reply in ONE short sentence.\n"
            "5. Your output is spoken aloud — shorter is always better."
        )

    messages.append({
        "role": "system",
        "content": system_content,
    })

    # Append conversation history from session (Phase 2)
    # Only use the last 4 messages to avoid flooding phi3:mini's tiny 4K context window
    if conversation_history:
        messages.extend(conversation_history[-4:])

    # Append the current user message
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,  # get the full response at once
        "options": {
            "num_predict": 100,  # ~80 words max — enough to output JSON ARGS cleanly
            "temperature": 0.0 if conversation_history is None else 0.7,
        },
    }

    try:
        load_monitor.ollama_active = True
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
    finally:
        load_monitor.ollama_active = False


# ---------------------------------------------------------------------------
# Whisper helper — transcribe an audio file to text
# ---------------------------------------------------------------------------
def transcribe_audio(audio_path: str) -> str:
    """
    Transcribe audio file using faster-whisper (CTranslate2 backend).
    Optimized for low-latency voice assistant use (short utterances).
    """
    global whisper_model
    log.info(f"Transcribing: {audio_path}")
    try:
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
        # Evaluate segments generator immediately to force inference
        text = " ".join(seg.text.strip() for seg in segments).strip()
        log.info(f"Transcribed ({info.language}, {info.language_probability:.0%}): '{text}'")
        return text
    except Exception as e:
        log.warning(f"Whisper transcription failed ({e}). Re-initializing on CPU and retrying...")
        try:
            whisper_model = WhisperModel(
                WHISPER_MODEL_SIZE,
                device="cpu",
                compute_type="int8",
            )
            segments, info = whisper_model.transcribe(
                audio_path,
                language="en",
                beam_size=1,
                max_initial_timestamp=1.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
                condition_on_previous_text=False,
            )
            text = " ".join(seg.text.strip() for seg in segments).strip()
            log.info(f"Fallback Transcribed successfully: '{text}'")
            return text
        except Exception as fallback_err:
            log.error(f"Whisper fallback failed: {fallback_err}")
            raise fallback_err


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


def _parse_schedule_datetime(msg: str) -> tuple[str | None, float | None, int | None]:
    """
    Extract event summary, hours_from_now, and duration from a natural language message.
    Returns (summary, hours_from_now, duration_minutes).
    Handles: 'schedule gym at 5pm', 'set a reminder for meeting at 3:30 pm', etc.
    """
    import re
    from datetime import datetime as dt_cls

    # Extract time pattern: "at 5pm", "at 3:30 PM", "at 17:00"
    time_match = re.search(
        r'(?:at|for|@)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)?',
        msg
    )

    hours_from_now = 1  # default: 1 hour from now
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        ampm = (time_match.group(3) or "").lower()

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        now = dt_cls.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # If the time is already past today, schedule for tomorrow
        if target <= now:
            from datetime import timedelta
            target = target + timedelta(days=1)

        diff = (target - now).total_seconds() / 3600
        hours_from_now = max(0.1, diff)  # at least 6 minutes out

    # Extract duration: "for 2 hours", "for 30 minutes", "for 1.5 hours"
    dur_match = re.search(r'for\s+(\d+\.?\d*)\s*(hour|hr|minute|min)', msg.lower())
    duration_minutes = 60  # default
    if dur_match:
        val = float(dur_match.group(1))
        unit = dur_match.group(2)
        if unit.startswith("min"):
            duration_minutes = int(val)
        else:
            duration_minutes = int(val * 60)

    # Extract summary: strip out the time/duration/command parts to get the event name
    summary = msg
    # Remove common command prefixes
    for prefix in [
        "can you put on my calendar", "put on my calendar",
        "can you put on calendar", "put on calendar",
        "fix my schedule", "set a reminder for", "set a reminder",
        "set reminder for", "set reminder", "add to my calendar",
        "add to calendar", "add event", "create event", "book",
        "remind me about", "remind me to", "can you put", "schedule",
        "add", "put", "can you"
    ]:
        if summary.lower().startswith(prefix):
            summary = summary[len(prefix):].strip()
            break

    # Remove the time and duration parts from the summary
    summary = re.sub(r'(?:at|for|@)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?', '', summary)
    summary = re.sub(r'for\s+\d+\.?\d*\s*(?:hour|hr|minute|min)s?', '', summary)
    summary = re.sub(r'\s+', ' ', summary).strip().strip('.,!?')

    if not summary:
        summary = "KIRA Scheduled Event"
    else:
        summary = summary.capitalize()

    return summary, hours_from_now, duration_minutes


def parse_and_run_tool(response_text: str, user_message: str, session_id: str | None) -> str | None:
    """
    Parse Ollama's response. If it contains a TOOL call, run it and return the result.
    Otherwise, return None.
    """
    # Match TOOL: <name> and ARGS: <json>
    tool_match = re.search(r'(?i)TOOL:\s*(\w+)', response_text)
    if not tool_match:
        return None

    tool_name = tool_match.group(1).lower().strip()
    
    # Try to find ARGS: {...}
    args_match = re.search(r'(?i)ARGS:\s*(\{.*?\})', response_text, re.DOTALL)
    args = {}
    if args_match:
        try:
            args = json.loads(args_match.group(1).strip())
        except Exception as e:
            log.warning(f"Failed to parse tool arguments JSON: {args_match.group(1)}. Error: {e}")

    log.info(f"[Tool Calling] Detected tool: {tool_name} with args: {args}")

    # 1. add_reminder
    if tool_name == "add_reminder":
        summary = args.get("summary")
        date_val = args.get("date")
        time_val = args.get("time")
        duration_minutes = args.get("duration_minutes", 60)

        # Fallback to natural language parsing of the original message
        nlp_summary, nlp_hours, nlp_duration = _parse_schedule_datetime(user_message)

        if not summary:
            summary = nlp_summary
        
        try:
            duration_minutes = int(duration_minutes) if duration_minutes is not None else 60
        except Exception:
            duration_minutes = 60

        if date_val or time_val:
            return add_reminder(
                summary,
                duration_minutes=duration_minutes,
                date_str=date_val,
                time_str=time_val
            )
        else:
            return add_reminder(
                summary,
                hours_from_now=nlp_hours,
                duration_minutes=duration_minutes
            )

    # 2. get_schedule
    elif tool_name == "get_schedule":
        date_val = args.get("date")
        query_val = args.get("query")
        
        # Guardrail: If the LLM mistakenly routed a task query to get_schedule
        if "task" in user_message.lower():
            if not session_id:
                return "I cannot list tasks without a valid session."
            log.info(f"[Tool Calling] Redirecting task-related query from get_schedule to list_tasks: '{user_message}'")
            keyword = query_val or args.get("query")
            if not keyword or keyword in ["today", "tomorrow", "yesterday", "friday", "sunday", "monday", "tuesday", "wednesday", "thursday", "saturday"]:
                keyword = None
            msg_lower = user_message.lower().strip()
            for pattern in [
                r"when do i have task\s+(.+?)\s+scheduled",
                r"when is my task\s+(.+?)\s+scheduled",
                r"when is the task\s+(.+?)\s+scheduled",
                r"when is\s+(.+?)\s+task scheduled",
                r"when is my\s+(.+?)\s+task scheduled",
                r"when is the\s+(.+?)\s+task scheduled",
                r"when do i have\s+(.+?)\s+scheduled",
                r"when is\s+(.+?)\s+scheduled",
                r"when is my\s+(.+?)\s+task",
                r"when is the\s+(.+?)\s+task",
                r"task\s+(.+?)\b",
            ]:
                match = re.search(pattern, msg_lower)
                if match:
                    potential = match.group(1).strip().strip("'\"")
                    if potential not in ["my schedule", "my calendar", "tasks", "my tasks", "schedule", "calendar"]:
                        keyword = potential
                        break
            return list_tasks(session_id, keyword=keyword)

        # Check if the user message actually mentions a date/day of week/relative date
        # to prevent Ollama from hallucinating/copying the current date into query searches.
        if query_val:
            date_keywords = ["today", "tomorrow", "yesterday", "monday", "tuesday", "wednesday", 
                             "thursday", "friday", "saturday", "sunday", "january", "february", 
                             "march", "april", "may", "june", "july", "august", "september", 
                             "october", "november", "december", "jan", "feb", "mar", "apr", "jun", 
                             "jul", "aug", "sep", "oct", "nov", "dec", "this week", "next week"]
            has_date_mention = any(k in user_message.lower() for k in date_keywords) or re.search(r'\b\d{1,2}(?:st|nd|rd|th)?\b', user_message)
            if not has_date_mention:
                log.info(f"[Tool Calling] Overriding hallucinated date constraint for query search: '{date_val}' -> None")
                date_val = None

        return get_schedule(date_str=date_val, query=query_val)

    # 3. add_task
    elif tool_name == "add_task":
        if not session_id:
            return "I cannot add tasks without a valid session."
        summary = args.get("summary")
        if not summary:
            summary = user_message.strip()
        return add_task(session_id, summary)

    # 4. mark_done
    elif tool_name == "mark_done":
        if not session_id:
            return "I cannot manage tasks without a valid session."
        keyword = args.get("keyword")
        if not keyword:
            keyword = user_message.strip()
        return mark_done(session_id, keyword)

    # 5. list_tasks
    elif tool_name == "list_tasks":
        if not session_id:
            return "I cannot list tasks without a valid session."
        keyword = args.get("keyword")
        
        # If the LLM failed to extract a keyword, but the user was clearly asking about a specific task
        if not keyword:
            msg_lower = user_message.lower().strip()
            # Clean up common phrasing to isolate the task keyword
            for pattern in [
                r"when do i have task\s+(.+?)\s+scheduled",
                r"when is my task\s+(.+?)\s+scheduled",
                r"when is the task\s+(.+?)\s+scheduled",
                r"when is\s+(.+?)\s+task scheduled",
                r"when is my\s+(.+?)\s+task scheduled",
                r"when is the\s+(.+?)\s+task scheduled",
                r"when do i have\s+(.+?)\s+scheduled",
                r"when is\s+(.+?)\s+scheduled",
                r"when is my\s+(.+?)\s+task",
                r"when is the\s+(.+?)\s+task",
            ]:
                match = re.search(pattern, msg_lower)
                if match:
                    potential = match.group(1).strip().strip("'\"")
                    if potential not in ["my schedule", "my calendar", "tasks", "my tasks", "schedule", "calendar"]:
                        keyword = potential
                        log.info(f"[Tool Calling] Regex extracted task keyword from user message: '{keyword}'")
                        break
        return list_tasks(session_id, keyword=keyword)

    log.warning(f"Unknown tool requested: {tool_name}")
    return None


def prepend_reminders(response_text: str, session_id: str | None) -> str:
    """
    Check for pending hourly reminders and prepend them to the response.
    This way KIRA naturally speaks the reminders before answering.
    """
    if not session_id:
        return response_text

    reminders = get_pending_reminders(session_id)
    if not reminders:
        return response_text

    reminder_block = " ".join(reminders)
    log.info(f"[Tasks] Injecting {len(reminders)} reminder(s) for session {session_id[:8]}...")
    return f"{reminder_block} Anyway, {response_text}"


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


@app.get("/alerts")
async def get_alerts():
    """
    Endpoint for the phone client to poll for productivity alerts.
    Returns any pending alerts and clears them.
    """
    alerts = monitor.get_and_clear_alerts()
    alert_msg = alerts[0] if alerts else None
    return {
        "alerts": alerts,
        "alert": alert_msg,
        "message": alert_msg,
        "status": "success" if alert_msg else "no_alerts"
    }


@app.post("/chat", response_model=KiraResponse)
async def chat_text(req: ChatRequest):
    """
    Text-based chat endpoint — useful for testing without voice.
    Send a JSON body: {"message": "your question here", "session_id": "optional-uuid"}
    """
    log.info(f"[/chat] Received: '{req.message}' (session: {req.session_id or 'none'})")

    load_monitor.active_requests += 1
    start_total = time.time()
    ollama_time = 0.0
    status = "success"
    response_text = ""
    error_msg = None

    try:
        # Get conversation history for this session
        history = get_session_history(req.session_id)

        # Phase 1: Intent detection (Query Ollama WITHOUT history to avoid conversational bias)
        t_ollama_1 = time.time()
        ollama_response = await query_ollama(req.message, conversation_history=None)
        ollama_time += (time.time() - t_ollama_1)

        # Check if the AI wants to call a tool
        tool_result = parse_and_run_tool(ollama_response, req.message, req.session_id)
        if tool_result is not None:
            response_text = tool_result
            intercepted = True
            log.info(f"[/chat] Tool call result: '{response_text}'")
        else:
            # Phase 2: If no tool was called, and history exists, query Ollama WITH history for context
            if history:
                log.info("[/chat] No tool detected, querying Ollama with history for conversational response...")
                t_ollama_2 = time.time()
                response_text = await query_ollama(req.message, conversation_history=history)
                ollama_time += (time.time() - t_ollama_2)
            else:
                response_text = ollama_response
            intercepted = False
            log.info(f"[/chat] Response: '{response_text[:80]}...'")

        # Phase 3: Prepend any pending hourly reminders
        response_text = prepend_reminders(response_text, req.session_id)

        # Phase 2: Check if Gemini should be suggested
        suggest_gemini = needs_gemini(response_text) if not intercepted else False

        # Save this exchange to session history
        # If a tool was run, format it with TOOL/ARGS/RESULT details to maintain tool context in history
        history_response = f"{ollama_response.strip()}\nRESULT: {response_text}" if intercepted else response_text
        update_session(req.session_id, req.message, history_response)

        return KiraResponse(
            response=response_text,
            timestamp=datetime.now().isoformat(),
            session_id=req.session_id,
            gemini_suggested=suggest_gemini,
        )
    except Exception as e:
        status = "error"
        error_msg = str(e)
        raise e
    finally:
        total_time = time.time() - start_total
        load_monitor.active_requests -= 1
        load_monitor.add_history_entry({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "endpoint": "/chat",
            "input": req.message,
            "output": error_msg or response_text,
            "whisper_time": 0.0,
            "ollama_time": ollama_time,
            "gemini_time": 0.0,
            "total_time": total_time,
            "status": status
        })


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

    load_monitor.active_requests += 1
    start_total = time.time()
    whisper_time = 0.0
    ollama_time = 0.0
    status = "success"
    response_text = ""
    transcription = ""
    error_msg = None

    # Save uploaded audio to a temp file for Whisper
    suffix = os.path.splitext(audio.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Step 1: Transcribe audio → text
        load_monitor.whisper_active = True
        t_whisper = time.time()
        try:
            transcription = transcribe_audio(tmp_path)
        finally:
            whisper_time = time.time() - t_whisper
            load_monitor.whisper_active = False

        if not transcription:
            response_text = "I didn't catch that. Could you say it again?"
            return KiraResponse(
                transcription="",
                response=response_text,
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
            )

        # Step 2: Get conversation history for context
        history = get_session_history(session_id)

        # Step 3: Intent detection (Query Ollama WITHOUT history to avoid conversational bias)
        t_ollama_1 = time.time()
        ollama_response = await query_ollama(transcription, conversation_history=None)
        ollama_time += (time.time() - t_ollama_1)

        # Check if the AI wants to call a tool
        tool_result = parse_and_run_tool(ollama_response, transcription, session_id)
        if tool_result is not None:
            response_text = tool_result
            intercepted = True
            log.info(f"[/voice] Tool call result: '{response_text}'")
        else:
            # Step 3b: If no tool was called, and history exists, query Ollama WITH history for context
            if history:
                log.info("[/voice] No tool detected, querying Ollama with history for conversational response...")
                t_ollama_2 = time.time()
                response_text = await query_ollama(transcription, conversation_history=history)
                ollama_time += (time.time() - t_ollama_2)
            else:
                response_text = ollama_response
            intercepted = False
            log.info(f"[/voice] Response: '{response_text[:80]}...'")

        # Phase 3: Prepend any pending hourly reminders
        response_text = prepend_reminders(response_text, session_id)

        # Step 4: Check if Gemini should be suggested
        suggest_gemini = needs_gemini(response_text) if not intercepted else False

        # Step 5: Save this exchange to session history
        # If a tool was run, format it with TOOL/ARGS/RESULT details to maintain tool context in history
        history_response = f"{ollama_response.strip()}\nRESULT: {response_text}" if intercepted else response_text
        update_session(session_id, transcription, history_response)

        return KiraResponse(
            transcription=transcription,
            response=response_text,
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            gemini_suggested=suggest_gemini,
        )
    except Exception as e:
        status = "error"
        error_msg = str(e)
        raise e
    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            
        total_time = time.time() - start_total
        load_monitor.active_requests -= 1
        load_monitor.add_history_entry({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "endpoint": "/voice",
            "input": transcription or "[Empty/Unintelligible]",
            "output": error_msg or response_text,
            "whisper_time": whisper_time,
            "ollama_time": ollama_time,
            "gemini_time": 0.0,
            "total_time": total_time,
            "status": status
        })


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

    load_monitor.active_requests += 1
    start_total = time.time()
    gemini_time = 0.0
    status = "success"
    gemini_response = ""
    error_msg = None

    if not is_gemini_available():
        status = "error"
        error_msg = "Gemini API key not configured."
        load_monitor.active_requests -= 1
        load_monitor.add_history_entry({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "endpoint": "/gemini",
            "input": req.prompt,
            "output": error_msg,
            "whisper_time": 0.0,
            "ollama_time": 0.0,
            "gemini_time": 0.0,
            "total_time": time.time() - start_total,
            "status": status
        })
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured. Set GEMINI_API_KEY environment variable.",
        )

    try:
        # Get conversation history for context
        history = get_session_history(req.session_id)

        # Query Gemini
        load_monitor.gemini_active = True
        t_gemini = time.time()
        try:
            gemini_response = await query_gemini(req.prompt, conversation_history=history)
        finally:
            gemini_time = time.time() - t_gemini
            load_monitor.gemini_active = False

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
    except Exception as e:
        status = "error"
        error_msg = str(e)
        raise e
    finally:
        total_time = time.time() - start_total
        load_monitor.active_requests -= 1
        load_monitor.add_history_entry({
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "endpoint": "/gemini",
            "input": req.prompt,
            "output": error_msg or gemini_response,
            "whisper_time": 0.0,
            "ollama_time": 0.0,
            "gemini_time": gemini_time,
            "total_time": total_time,
            "status": status
        })


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
# Phase 3: Task management endpoints
# ---------------------------------------------------------------------------

@app.get("/tasks/{session_id}")
async def get_tasks(session_id: str):
    """List all active hourly-reminder tasks for a session."""
    return {
        "session_id": session_id,
        "task_count": get_task_count(session_id),
        "tasks": list_tasks(session_id),
    }


@app.delete("/tasks/{session_id}/{keyword}")
async def delete_task(session_id: str, keyword: str):
    """Manually mark a task as done by keyword."""
    result = mark_done(session_id, keyword)
    return {"session_id": session_id, "result": result}


@app.get("/")
async def get_dashboard():
    """Serves the KIRA server load monitor dashboard."""
    dashboard_path = Path(__file__).parent / "static" / "index.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path)
    return HTMLResponse("<h1>KIRA Load Monitor Dashboard not found. Check server/static/index.html</h1>", status_code=404)


@app.get("/api/stats")
async def get_load_stats():
    """Returns the current system load and KIRA AI metrics."""
    return load_monitor.get_stats()


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
