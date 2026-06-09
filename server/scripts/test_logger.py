"""
test_logger.py — Verify dataset logging functionality.
Run from repository root: python server/scripts/test_logger.py
"""

import os
import sys
import json
from pathlib import Path

# Add server directory to path
sys.path.append(str(Path(__file__).parent.parent))

from services.dataset_logger import log_interaction, DATA_PATH

def main():
    print("=" * 60)
    print("Running Dataset Logger Tests")
    print("=" * 60)
    
    # 1. Clear existing dataset if it exists (for clean test run)
    if DATA_PATH.exists():
        os.remove(DATA_PATH)
        
    # 2. Log test interactions
    log_interaction("hello", "Hi there, I am KIRA.")
    log_interaction("what's the time?", "It is 10 PM.")
    
    # 3. Read back and verify
    assert DATA_PATH.exists(), "Dataset file was not created"
    
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    print(f"Logged lines: {lines}")
    assert len(lines) == 2, f"Expected 2 logged entries, got {len(lines)}"
    
    # Verify JSON structure
    entry1 = json.loads(lines[0])
    assert "messages" in entry1
    assert len(entry1["messages"]) == 3
    assert entry1["messages"][0]["role"] == "system"
    assert entry1["messages"][1]["role"] == "user" and entry1["messages"][1]["content"] == "hello"
    assert entry1["messages"][2]["role"] == "assistant" and entry1["messages"][2]["content"] == "Hi there, I am KIRA."
    
    # Clean up test file
    if DATA_PATH.exists():
        os.remove(DATA_PATH)
        
    print("Dataset logger test passed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
