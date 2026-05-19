# KIRA — Personal AI Assistant | Full Project Context

## What this project is
KIRA is a voice-first personal AI assistant built from scratch.
It runs across two devices:
- **Laptop (Windows, RTX 3050 6GB, 24GB RAM)** — the brain/server
- **Android phone (4GB RAM, 64GB storage) via Termux** — the ears and mouth

The laptop hosts the AI model locally using Ollama and exposes it via 
a Python API server. The phone captures voice, sends it to the laptop, 
gets a response, and speaks it back. When internet is off, a tiny 
offline model on the phone handles minimal tasks.

---

## Core Architecture

### Laptop (Server side)
- Ollama running phi3:mini locally as the primary brain
- Python FastAPI server that the phone hits over the network
- Ngrok tunnel so the phone can reach the laptop from outside WiFi
- Gemini API as fallback for complex tasks (asks permission before using)
- Background productivity monitor watching active windows

### Phone (Client side)
- Termux (installed via F-Droid) running Python
- Termux:API for microphone and speaker access
- Wake word detection — listens for trigger phrase
- Records voice → sends to laptop server → receives response → speaks it
- Small offline model for when internet is unavailable

---

## 8 Features to Build

### 1. Custom Voice
- Piper TTS for text-to-speech on the phone
- Custom voice profile so it doesn't sound generic
- Voice output through phone speaker

### 2. Study Material Search
- User says a topic → JARVIS searches the web for best resources
- Returns articles, YouTube videos, documentation links
- Presents results conversationally, not as a raw list dump
- Uses Brave Search API (free tier, 2000 searches/month)

### 3. Reminders
- Set reminders by voice
- Pushes directly to Google Calendar via Google Calendar API
- Shows up on phone automatically since phone uses same Google account

### 4. Schedule Builder
- User dumps tasks for the day in plain speech
- JARVIS builds a structured timetable
- Pushes events to Google Calendar with proper time slots
- Accessible on phone instantly

### 5. GitHub Repo Search
- User asks about a topic or project idea
- JARVIS searches GitHub for similar/relevant repos
- Returns repo name, description, star count, language, and link
- Uses GitHub public API (no key needed for basic search)
- Suggests top 3-5 most relevant results conversationally

### 6. Gemini Fallback
- phi3:mini handles 90% of tasks
- For genuinely complex tasks, JARVIS asks permission first:
  "This seems complex, should I use Gemini for this?"
- Only calls Gemini API after explicit user approval
- Gemini API key already available via Google Pro subscription

### 7. Offline Mode
- When internet is unavailable, a quantized tiny model runs on phone
- Handles minimal tasks: read schedule, set timer, basic questions
- Automatically detects connectivity and switches modes
- Switches back to laptop model when internet returns

### 8. Productivity Monitor
- Runs as background process on laptop
- Monitors active window/app every 60 seconds
- If unproductive app (YouTube, games, etc.) detected for more than
  a set threshold (e.g. 15 minutes), triggers voice alert through phone
- User can configure which apps count as unproductive
- User can set focus sessions where all alerts are suppressed

---

## Tech Stack

| Layer | Technology |
|---|---|
| Primary AI model | phi3:mini via Ollama |
| Fallback AI | Gemini API |
| Offline AI | TinyLlama or Phi-3 quantized (GGUF) |
| Server framework | FastAPI (Python) |
| Voice capture | Termux:API + PyAudio |
| Speech to text | Whisper tiny or Vosk |
| Text to speech | Piper TTS |
| Wake word | openWakeWord |
| Web search | Brave Search API |
| GitHub search | GitHub public REST API |
| Calendar/Reminders | Google Calendar API |
| Tunnel | Ngrok |
| IDE | Google Antigravity |
| Phone runtime | Termux (F-Droid version) |

---

## Project Folder Structure