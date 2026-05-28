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
REMINDER_INTERVAL = 30  # 30 seconds


# ---------------------------------------------------------------------------
# In-memory task store
# ---------------------------------------------------------------------------
# Structure: {session_id: [Task, Task, ...]}
# Each Task is a dict with: summary, created_at, last_reminded_at
_tasks: dict[str, list[dict]] = {}


def add_task(session_id: str, summary: str) -> str:
    """
    Add a new 30-second-reminder task (or multiple tasks) for a session.
    Returns a confirmation string for KIRA to speak.
    """
    import re
    if session_id not in _tasks:
        _tasks[session_id] = []

    # Clean up prefixes like "task " or "tasks " if they got included
    def clean_item(text: str) -> str:
        text = text.strip()
        # Remove leading "task " or "tasks " case-insensitively
        text = re.sub(r'^(?i)tasks?\s+', '', text)
        return text.strip()

    # Split by " and ", " or ", and commas ","
    # E.g. "buy milk, clean room and study python"
    split_pattern = re.compile(r'\s+(?:and|or)\s+|,\s*', re.IGNORECASE)
    parts = [clean_item(p) for p in split_pattern.split(summary) if p.strip()]

    if not parts:
        return "I couldn't understand the task description."

    added_summaries = []
    already_had = []

    now = time.time()
    for part in parts:
        # Avoid duplicates (case-insensitive check)
        exists = False
        for t in _tasks[session_id]:
            if t["summary"].lower() == part.lower():
                exists = True
                already_had.append(part)
                break
        if not exists:
            _tasks[session_id].append({
                "summary": part,
                "created_at": now,
                "last_reminded_at": now,  # don't nag immediately — first reminder after 30s
            })
            added_summaries.append(part)
            log.info(f"[Tasks] Added for {session_id[:8]}...: '{part}'")

    # Construct the speech response
    msg_parts = []
    if added_summaries:
        if len(added_summaries) == 1:
            msg_parts.append(f"Got it, I'll remind you about '{added_summaries[0]}' every 30 seconds until it's done.")
        else:
            joined = ", ".join(f"'{s}'" for s in added_summaries[:-1]) + f" and '{added_summaries[-1]}'"
            msg_parts.append(f"Got it, I'll remind you about {joined} every 30 seconds until they are done.")
    
    if already_had:
        if len(already_had) == 1:
            msg_parts.append(f"You already have '{already_had[0]}' on your task list.")
        else:
            joined = ", ".join(f"'{s}'" for s in already_had[:-1]) + f" and '{already_had[-1]}'"
            msg_parts.append(f"You already have {joined} on your task list.")

    return " ".join(msg_parts)


def get_pending_reminders(session_id: str) -> list[str]:
    """
    Returns a list of reminder strings for tasks that are due (≥30s since
    last reminded). Also updates last_reminded_at so we don't re-fire
    until the next 30s.
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


def get_all_pending_reminders(session_id: Optional[str] = None) -> list[str]:
    """
    Returns a list of reminder strings for tasks that are due, specifying only the number of pending tasks.
    Also updates last_reminded_at.
    """
    if not _tasks:
        return []

    now = time.time()
    due = []

    target_sessions = [session_id] if session_id else list(_tasks.keys())

    for sid in target_sessions:
        task_list = _tasks.get(sid, [])
        if not task_list:
            continue

        # Check if ANY task in the session is due for a reminder
        any_due = False
        for task in task_list:
            elapsed = now - task["last_reminded_at"]
            if elapsed >= REMINDER_INTERVAL:
                any_due = True
                break

        if any_due:
            count = len(task_list)
            if count == 1:
                due.append("Reminder: you have 1 pending task.")
            else:
                due.append(f"Reminder: you have {count} pending tasks.")

            # Reset last_reminded_at for ALL tasks in this session so they stay in sync
            for task in task_list:
                task["last_reminded_at"] = now
            log.info(f"[Tasks] Reminded session {sid[:8]}...: {count} pending tasks.")

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
            if not _tasks[session_id]:
                del _tasks[session_id]
            return f"Nice! Marked '{removed['summary']}' as done."

    # 2. Fallback 1: If there is only one task, assume the user is referring to it
    if len(_tasks[session_id]) == 1:
        removed = _tasks[session_id].pop(0)
        log.info(f"[Tasks] Completed single task via fallback for {session_id[:8]}...: '{removed['summary']}'")
        if not _tasks[session_id]:
            del _tasks[session_id]
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
            if not _tasks[session_id]:
                del _tasks[session_id]
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
