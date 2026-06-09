"""
database.py — KIRA Phase 6
Handles SQLite database persistence for conversation sessions and task reminders.
"""

import sqlite3
import os
import logging
from pathlib import Path

log = logging.getLogger("kira-server.database")
DB_PATH = Path(__file__).parent.parent / "config" / "kira.db"

def init_db():
    """Initialize SQLite tables for session memory and task reminders."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    
    # 1. Create sessions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # 2. Create messages table (conversation history)
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        role TEXT,
        content TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
    )
    """)
    
    # 3. Create tasks table (Nag to-do list)
    c.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        summary TEXT,
        status TEXT DEFAULT 'pending',
        created_at REAL,
        last_reminded_at REAL
    )
    """)
    
    conn.commit()
    conn.close()
    log.info(f"SQLite database initialized at: {DB_PATH}")

# Initialize database at import time to ensure tables exist
init_db()

# ---------------------------------------------------------------------------
# Session History Persistence
# ---------------------------------------------------------------------------
def save_chat_message(session_id: str, role: str, content: str):
    """Save a single chat message (user or assistant) to the database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO sessions (session_id) VALUES (?)", (session_id,))
        c.execute("INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)", (session_id, role, content))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error saving chat message to DB: {e}")

def load_chat_history(session_id: str, limit: int = 4) -> list[dict]:
    """Retrieve chat history for a session, sorted in chronological order."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT role, content FROM messages 
            WHERE session_id = ? 
            ORDER BY id DESC LIMIT ?
        """, (session_id, limit))
        rows = c.fetchall()
        conn.close()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
    except Exception as e:
        log.error(f"Error loading chat history from DB: {e}")
        return []

def clear_chat_history(session_id: str):
    """Delete all message history associated with a session ID."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()
        log.info(f"Cleared session history for: {session_id}")
    except Exception as e:
        log.error(f"Error clearing chat history: {e}")

# ---------------------------------------------------------------------------
# Tasks Persistence
# ---------------------------------------------------------------------------
def save_task(session_id: str, summary: str, created_at: float, last_reminded_at: float):
    """Save a new pending task reminder to the database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            INSERT INTO tasks (session_id, summary, status, created_at, last_reminded_at)
            VALUES (?, ?, 'pending', ?, ?)
        """, (session_id, summary, created_at, last_reminded_at))
        conn.commit()
        conn.close()
        log.info(f"Saved task to DB: '{summary}' for session {session_id[:8]}...")
    except Exception as e:
        log.error(f"Error saving task to DB: {e}")

def update_task_reminded(session_id: str, summary: str, last_reminded_at: float):
    """Update the last reminded timestamp of a pending task."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            UPDATE tasks SET last_reminded_at = ? 
            WHERE session_id = ? AND summary = ? AND status = 'pending'
        """, (last_reminded_at, session_id, summary))
        conn.commit()
        conn.close()
    except Exception as e:
        log.error(f"Error updating task reminded state in DB: {e}")

def complete_task(session_id: str, summary: str):
    """Mark a pending task as done/completed in the database."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        c.execute("""
            UPDATE tasks SET status = 'done' 
            WHERE session_id = ? AND summary = ? AND status = 'pending'
        """, (session_id, summary))
        conn.commit()
        conn.close()
        log.info(f"Completed task in DB: '{summary}' for session {session_id[:8]}...")
    except Exception as e:
        log.error(f"Error marking task complete in DB: {e}")

def load_pending_tasks() -> dict[str, list[dict]]:
    """Load all pending tasks from SQLite to synchronize memory on server startup."""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT session_id, summary, created_at, last_reminded_at FROM tasks WHERE status = 'pending'")
        rows = c.fetchall()
        conn.close()
        
        tasks_dict = {}
        for r in rows:
            sid = r["session_id"]
            if sid not in tasks_dict:
                tasks_dict[sid] = []
            tasks_dict[sid].append({
                "summary": r["summary"],
                "created_at": r["created_at"],
                "last_reminded_at": r["last_reminded_at"]
            })
        log.info(f"Loaded {len(rows)} pending tasks from database.")
        return tasks_dict
    except Exception as e:
        log.error(f"Error loading pending tasks from DB: {e}")
        return {}
