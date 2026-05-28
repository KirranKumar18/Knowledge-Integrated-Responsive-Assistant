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
REMINDER_INTERVAL = 10  # 10 seconds


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------
# Structure: {session_id: [Task, Task, ...]}
# Each Task is a dict with: summary, created_at, last_reminded_at
_tasks: dict[str, list[dict]] = {}


def add_task(session_id: str, summary: str) -> str:
    """
    Add a new 10-second-reminder task for a session.
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
        "last_reminded_at": now,  # don't nag immediately — first reminder after 10s
    })
    log.info(f"[Tasks] Added for {session_id[:8]}...: '{summary}'")
    return f"Got it, I'll remind you about '{summary}' every 10 seconds until it's done."


def get_pending_reminders(session_id: str) -> list[str]:
    """
    Returns a list of reminder strings for tasks that are due (≥10s since
    last reminded). Also updates last_reminded_at so we don't re-fire
    until the next 10s.
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


def get_all_pending_reminders() -> list[str]:
    """
    Returns a list of reminder strings for tasks that are due across all sessions.
    Also updates last_reminded_at.
    """
    if not _tasks:
        return []

    now = time.time()
    due = []

    for session_id, task_list in _tasks.items():
        for task in task_list:
            elapsed = now - task["last_reminded_at"]
            if elapsed >= REMINDER_INTERVAL:
                due.append(f"Reminder: you still need to {task['summary'].lower()}.")
                task["last_reminded_at"] = now  # reset the clock
                log.info(f"[Tasks] Reminded about: '{task['summary']}' (session: {session_id[:8]}...)")

    return due



def mark_done(session_id: str, keyword: str) -> str:
    """
    Fuzzy-match a keyword against active tasks and remove the first match.
    Returns a confirmation string for KIRA to speak.
    """
    import re
    if session_id not in _tasks or not _tasks[session_id]:
        return "You don't have any active tasks right now."

    keyword_lower = keyword.lower().strip()

    # 1. Try exact substring match first (keyword in task summary, or vice versa)
    for i, task in enumerate(_tasks[session_id]):
        if keyword_lower in task["summary"].lower() or task["summary"].lower() in keyword_lower:
            removed = _tasks[session_id].pop(i)
            log.info(f"[Tasks] Completed for {session_id[:8]}...: '{removed['summary']}'")
            return f"Nice! Marked '{removed['summary']}' as done."

    # 2. Fallback 1: If there is only one task, assume the user is referring to it
    if len(_tasks[session_id]) == 1:
        removed = _tasks[session_id].pop(0)
        log.info(f"[Tasks] Completed single task via fallback for {session_id[:8]}...: '{removed['summary']}'")
        return f"Nice! Marked '{removed['summary']}' as done."

    # 3. Fallback 2: Token-based overlap matching (for multiple tasks)
    # Filter out common stop/instruction words
    stop_words = {
        "i", "completed", "the", "task", "finished", "done", "my", "to", "me", 
        "about", "for", "a", "an", "and", "of", "it", "have", "marked", "mark"
    }
    keyword_words = [w for w in re.split(r'\W+', keyword_lower) if w and w not in stop_words]
    
    if keyword_words:
        best_match_idx = -1
        max_overlap = 0
        for i, task in enumerate(_tasks[session_id]):
            task_words = set(re.split(r'\W+', task["summary"].lower()))
            overlap = sum(1 for w in keyword_words if w in task_words)
            if overlap > max_overlap:
                max_overlap = overlap
                best_match_idx = i
        
        if best_match_idx != -1 and max_overlap > 0:
            removed = _tasks[session_id].pop(best_match_idx)
            log.info(f"[Tasks] Completed task via token overlap match ({max_overlap} words) for {session_id[:8]}...: '{removed['summary']}'")
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
