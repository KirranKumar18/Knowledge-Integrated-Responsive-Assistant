# KIRA — Service Integration Guide

This document explains exactly how KIRA connects to and uses its external services: **Google Calendar**, **Productivity Monitor**, and **Task Reminder**. It covers the full data flow from the moment you speak, to how KIRA decides to invoke a service, to how the result comes back to you as spoken audio.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                        KIRA SERVER (server.py)                         │
│                                                                        │
│  ┌──────────┐    ┌──────────────────┐    ┌───────────────────────────┐ │
│  │  Whisper  │───>│  Intent Router   │───>│  Handler / Service Layer  │ │
│  │ (speech   │    │  (two-pass flow) │    │                           │ │
│  │  to text) │    └────────┬─────────┘    │  ┌──────────────────────┐ │ │
│  └──────────┘              │              │  │ calendar_handler.py  │ │ │
│                            ▼              │  │ (Google Calendar API) │ │ │
│  ┌──────────┐      1. Intent Check        │  └──────────────────────┘ │ │
│  │  Ollama   │<─── (No history, T=0.0)    │                           │ │
│  │ (phi3:mini│     If tool matches:       │  ┌──────────────────────┐ │ │
│  │  for AI   │       → Call handler       │  │ task_reminder.py     │ │ │
│  │  routing) │                            │  │ (Hourly nag tasks)   │ │ │
│  └──────────┘      2. Conversational      │  └──────────────────────┘ │ │
│                    (With history, T=0.7)  │                           │ │
│                      → General Chat       │  ┌──────────────────────┐ │ │
│                                           │  │ productivity_monitor │ │ │
│                                           │  │ (Window tracking)    │ │ │
│                                           │  └──────────────────────┘ │ │
│                                           └───────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
         ▲                                           │
         │ Audio (voice)                             │ JSON response
         │                                           ▼
┌────────────────────────────────────────────────────────────────────────┐
│                    CLIENT (client.py on phone)                         │
│        Records voice → Sends to server → Speaks response via TTS       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## How the Intent Router Works

When you say something to KIRA, `server.py` runs your query through a **two-pass intent classification and routing pipeline**. This bypasses rigid keyword matching and lets `phi3:mini` handle flexible, natural language variations without getting biased by conversational history.

```
                  User input (transcription)
                              │
                              ▼
        ┌───────────────────────────────────────────┐
        │ Pass 1: Intent Detection (Ollama)         │
        │ - Query Ollama WITHOUT history            │
        │ - Use Tool-Calling System Prompt          │
        │ - Set Temperature = 0.0                   │
        └─────────────────────┬─────────────────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
       Tool block found?               No tool block found?
    (e.g., TOOL: add_reminder)             (Conversational)
             │                                 │
             ▼                                 ▼
   ┌───────────────────┐             ┌───────────────────┐
   │ execute tool via  │             │ Has history?      │
   │ parse_and_run_tool│             └─────────┬─────────┘
   └───────────────────┘                       │
                                    ┌──────────┴──────────┐
                                    ▼                     ▼
                                   YES                    NO
                                    │                     │
                                    ▼                     ▼
                        ┌──────────────────────┐  ┌───────────────┐
                        │ Pass 2: Conversational│  │ Return Pass 1 │
                        │ - Query with history │  │ response      │
                        │ - Conversational-only│  │ directly      │
                        │   prompt (no tools)  │  └───────────────┘
                        │ - Set Temp = 0.7     │
                        └──────────────────────┘
```

### Relevant Code (server.py):

```python
# Pass 1: Query Ollama WITHOUT history to check for tool calls
ollama_response = await query_ollama(transcription, conversation_history=None)

# Check if the AI wants to call a tool
tool_result = parse_and_run_tool(ollama_response, transcription, session_id)
if tool_result is not None:
    response_text = tool_result
    intercepted = True
else:
    # Pass 2: If no tool was called and history exists, query Ollama WITH history
    if history:
        response_text = await query_ollama(transcription, conversation_history=history)
    else:
        response_text = ollama_response
    intercepted = False
```

---

## Service 1: Google Calendar

### Files Involved
| File | Role |
|------|------|
| `server/handlers/calendar_handler.py` | Core logic — OAuth2 auth, read events, create events |
| `server/config/credentials.json` | Google Cloud OAuth2 credentials (downloaded from Cloud Console) |
| `server/config/token.json` | Auto-generated — stores access + refresh tokens |
| `server/scripts/setup_calendar.py` | One-time setup script to authorize KIRA |

### Authentication Flow (One-time Setup)
1. You run `python server/scripts/setup_calendar.py`.
2. It reads `server/config/credentials.json` and opens a browser window for Google Account OAuth login.
3. Upon approval, tokens are saved to `server/config/token.json`. KIRA uses this token to run calls in the background and refreshes it automatically.

### Reading Your Schedule — `get_schedule()`
- **Ollama Tool Call**: `TOOL: get_schedule` | `ARGS: {}`
- **NLP Examples**: *"what's on my calendar?"*, *"what is my schedule today?"*, *"do I have any upcoming events?"*
- **Execution**: The server executes `get_schedule()` in `calendar_handler.py`, fetching the primary calendar's next 5 events using the Google Calendar API, and outputs a spoken-friendly description.

### Adding Calendar Events — `add_reminder()`
- **Ollama Tool Call**: `TOOL: add_reminder` | `ARGS: {"summary": "Event Name", "time": "HH:MM", "duration_minutes": 60}`
- **NLP Examples**: *"can you put gym in my calendar at 6 pm?"*, *"remind me about dentist tomorrow at 10 AM for 30 minutes"*, *"schedule standup at 9"*
- **Execution**:
  1. Ollama extracts the core `summary` (e.g. "Gym session"), target `time` (e.g. "18:00"), and `duration_minutes`.
  2. If the parsed time is relative (or if JSON parsing fails due to truncation), our robust fallback `_parse_schedule_datetime()` extracts the event name and relative start time from the original user text.
  3. The server calls `add_reminder(...)` in `calendar_handler.py` to insert the event into Google Calendar.

---

## Service 2: Task Reminder (To-Do List)

Provides a spoken, hourly-reminder to-do engine. Tasks are saved in memory and KIRA nags the user once every hour about pending tasks before responding to any query.

- **Add Task**: `TOOL: add_task` | `ARGS: {"summary": "task name"}`
  - *Example*: *"I need to buy milk"* or *"don't let me forget to call Mom"*
- **List Tasks**: `TOOL: list_tasks` | `ARGS: {}`
  - *Example*: *"what are my tasks?"* or *"show my pending tasks"*
- **Mark Completed**: `TOOL: mark_done` | `ARGS: {"keyword": "task name"}`
  - *Example*: *"I finished buying milk"* or *"mark call Mom as done"*

---

## Service 3: Productivity Monitor

A passive background service that runs as a daemon thread and watches your active window on your laptop every 5 seconds.

- **How It Works**:
  - Monitors window titles using `pygetwindow`.
  - Increments a distraction timer if window titles contain distracting keywords (e.g. `YouTube`, `Reddit`, `Twitter`, `Netflix`).
  - Decays distraction time at **2x speed** if you focus back on a productive window (e.g. `VS Code`, `Terminal`).
  - Logs a warning alert to the server console if active distraction reaches **5 continuous minutes**.

---

## Summary: Endpoint Routing Mapping

| User Intent | Ollama Tool Response | Server Action |
|---|---|---|
| Read schedule | `TOOL: get_schedule` | Calls Google Calendar API to list events |
| Schedule event | `TOOL: add_reminder` | Calls Google Calendar API to insert event |
| Add reminder task | `TOOL: add_task` | Adds task to in-memory hourly list |
| List tasks | `TOOL: list_tasks` | Lists current pending hourly tasks |
| Complete task | `TOOL: mark_done` | Marks matched task as done and stops reminding |
| Casual conversation | None (`NO_TOOL`) | Runs conversation pipeline with session history |
