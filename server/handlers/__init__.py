"""
handlers/ — KIRA server request handler modules.

Handles calendar, Gemini fallback, and task reminders.
"""

from .gemini_handler import needs_gemini, query_gemini, is_gemini_available
from .calendar_handler import get_schedule, add_reminder
from .task_reminder import (
    add_task,
    get_pending_reminders,
    mark_done,
    list_tasks,
    get_task_count,
)
