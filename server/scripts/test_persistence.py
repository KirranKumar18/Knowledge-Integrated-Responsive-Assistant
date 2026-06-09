"""
test_persistence.py — Verify SQLite session message and task persistence.
Run from repository root: python server/scripts/test_persistence.py
"""

import os
import sys
import time
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.database import (
    save_chat_message,
    load_chat_history,
    clear_chat_history,
    save_task,
    complete_task,
    load_pending_tasks,
    update_task_reminded,
    DB_PATH
)

def test_chat_persistence():
    print("\n--- Testing Chat History Persistence ---")
    session_id = "test_sess_999"
    
    # 1. Clear existing history for test session
    clear_chat_history(session_id)
    
    # 2. Save test messages
    save_chat_message(session_id, "user", "Hello KIRA")
    save_chat_message(session_id, "assistant", "Hello! How can I help you today?")
    save_chat_message(session_id, "user", "What is the weather?")
    save_chat_message(session_id, "assistant", "It is sunny.")
    
    # 3. Load and assert limits
    history = load_chat_history(session_id, limit=2)
    print(f"Loaded last 2 messages: {history}")
    assert len(history) == 2, f"Expected 2 messages, got {len(history)}"
    assert history[0]["role"] == "user" and history[0]["content"] == "What is the weather?"
    assert history[1]["role"] == "assistant" and history[1]["content"] == "It is sunny."
    
    # Load all (limit=4)
    full_history = load_chat_history(session_id, limit=4)
    print(f"Loaded last 4 messages: {full_history}")
    assert len(full_history) == 4, f"Expected 4 messages, got {len(full_history)}"
    
    # 4. Clean up
    clear_chat_history(session_id)
    cleared_history = load_chat_history(session_id)
    assert len(cleared_history) == 0, "Expected cleared history to be empty"
    print("Chat history persistence test passed!")

def test_task_persistence():
    print("\n--- Testing Task Persistence ---")
    session_id = "test_sess_999"
    
    # 1. Save dummy tasks
    now = time.time()
    save_task(session_id, "buy bread", now, now)
    save_task(session_id, "clean windows", now, now)
    
    # 2. Load pending tasks
    pending = load_pending_tasks()
    print(f"Loaded pending tasks: {pending}")
    assert session_id in pending, "Expected test session to be in pending list"
    assert len(pending[session_id]) >= 2, "Expected at least 2 pending tasks"
    
    # Check details of one task
    task_summaries = [t["summary"] for t in pending[session_id]]
    assert "buy bread" in task_summaries
    assert "clean windows" in task_summaries
    
    # 3. Complete task and verify
    complete_task(session_id, "buy bread")
    pending_after = load_pending_tasks()
    task_summaries_after = [t["summary"] for t in pending_after.get(session_id, [])]
    print(f"Pending tasks after complete: {task_summaries_after}")
    assert "buy bread" not in task_summaries_after
    assert "clean windows" in task_summaries_after
    
    # Clean up by completing the second task too
    complete_task(session_id, "clean windows")
    print("Task persistence test passed!")

def main():
    print("=" * 60)
    print("Running SQLite Persistence Tests")
    print("=" * 60)
    
    try:
        test_chat_persistence()
        test_task_persistence()
        print("\nAll persistence tests passed successfully!")
    except AssertionError as e:
        print(f"\nTest Assertion Failed: {e}")
    except Exception as e:
        print(f"\nError during testing: {e}")
    print("=" * 60)

if __name__ == "__main__":
    main()
