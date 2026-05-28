"""
task_reminder.py — KIRA Phase 3
In-memory hourly task reminder engine.

When the user says something like "I need to finish my homework today",
KIRA stores the task and reminds them every 1 hour until they say it's done.

Tasks are in-memory only — they persist for the server's lifetime but are
lost on restart (consistent with how session history works).
"""

import time
import logging
from typing import Optional

log = logging.getLogger("kira-server.tasks")

# How often (in seconds) to nag the user about a pending task
REMINDER_INTERVAL = 3600  # 1 hour


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------
# Structure: {session_id: [Task, Task, ...]}
# Each Task is a dict with: summary, created_at, last_reminded_at
_tasks: dict[str, list[dict]] = {}


def add_task(session_id: str, summary: str) -> str:
    """
    Add a new hourly-reminder task for a session.
    Returns a confirmation string for KIRA to speak.
    """
    if session_id not in _tasks:
        _tasks[session_id] = []

    # Avoid duplicates (case-insensitive check)
    for t in _tasks[session_id]:
        if t["summary"].lower() == summary.lower():
            return f"You already have '{summary}' on your task list. I'll keep reminding you."

    now = time.time()
    _tasks[session_id].append({
        "summary": summary,
        "created_at": now,
        "last_reminded_at": now,  # don't nag immediately — first reminder after 1hr
    })
    log.info(f"[Tasks] Added for {session_id[:8]}...: '{summary}'")
    return f"Got it, I'll remind you about '{summary}' every hour until it's done."


def get_pending_reminders(session_id: str) -> list[str]:
    """
    Returns a list of reminder strings for tasks that are due (≥1hr since
    last reminded). Also updates last_reminded_at so we don't re-fire
    until the next hour.
    """
    if session_id not in _tasks or not _tasks[session_id]:
        return []

    now = time.time()
    due = []

    for task in _tasks[session_id]:
        elapsed = now - task["last_reminded_at"]
        if elapsed >= REMINDER_INTERVAL:
            due.append(f"Reminder: you still need to {task['summary'].lower()}.")
            task["last_reminded_at"] = now  # reset the clock
            log.info(f"[Tasks] Reminded {session_id[:8]}... about: '{task['summary']}'")

    return due


def mark_done(session_id: str, keyword: str) -> str:
    """
    Fuzzy-match a keyword against active tasks and remove the first match.
    Returns a confirmation string for KIRA to speak.
    """
    if session_id not in _tasks or not _tasks[session_id]:
        return "You don't have any active tasks right now."

    keyword_lower = keyword.lower().strip()

    # Try to find a task whose summary contains the keyword
    for i, task in enumerate(_tasks[session_id]):
        if keyword_lower in task["summary"].lower():
            removed = _tasks[session_id].pop(i)
            log.info(f"[Tasks] Completed for {session_id[:8]}...: '{removed['summary']}'")
            return f"Nice! Marked '{removed['summary']}' as done."

    return f"I couldn't find a task matching '{keyword}'. Say 'what are my tasks' to see your list."


def list_tasks(session_id: str, keyword: str | None = None) -> str:
    """
    Returns a spoken-friendly list of all active tasks, or a specific task if keyword is provided.
    """
    if session_id not in _tasks or not _tasks[session_id]:
        if keyword:
            return "no task"
        return "You don't have any active tasks right now."

    if keyword:
        keyword_lower = keyword.lower().strip()
        # Search for a matching task
        for task in _tasks[session_id]:
            if keyword_lower in task["summary"].lower():
                import datetime as dt_cls
                # Convert created_at to a spoken-friendly date and time
                dt = dt_cls.datetime.fromtimestamp(task["created_at"])
                date_str = dt.strftime("%A, %B %d at %I:%M %p")
                return f"Your task '{task['summary']}' is scheduled, created on {date_str}."
        
        return "no task"

    # Original logic (list all)
    task_names = [t["summary"] for t in _tasks[session_id]]

    if len(task_names) == 1:
        return f"You have one active task: {task_names[0]}."
    else:
        joined = ", ".join(task_names[:-1]) + f", and {task_names[-1]}"
        return f"You have {len(task_names)} active tasks: {joined}."


def get_task_count(session_id: str) -> int:
    """Returns the number of active tasks for a session."""
    return len(_tasks.get(session_id, []))
