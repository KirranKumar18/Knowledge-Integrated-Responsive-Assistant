"""
dataset_logger.py — KIRA Phase 5
Appends conversation turns in Hugging Face ChatML format to a fine-tuning JSONL dataset.
"""

import json
import logging
from pathlib import Path
import threading

log = logging.getLogger("kira-server.dataset")
DATA_PATH = Path(__file__).parent.parent / "data" / "fine_tuning_data.jsonl"
_lock = threading.Lock()

def log_interaction(user_prompt: str, assistant_response: str, system_prompt: str | None = None):
    """
    Log a user-assistant exchange into the training dataset.
    Appends as a single JSON line containing a 'messages' list.
    """
    if not user_prompt or not assistant_response:
        return

    # Default system prompt matching KIRA's persona if not specified
    if not system_prompt:
        system_prompt = (
            "You are KIRA, a personal AI voice assistant. "
            "Keep replies to 1-2 sentences maximum, casual and friendly, without markdown."
        )

    # Format matches Hugging Face SFTTrainer / Unsloth messages format
    sample = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_response}
        ]
    }

    try:
        DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _lock:
            with open(DATA_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")
        log.info(f"Interaction logged to fine-tuning dataset: '{user_prompt[:30]}...' -> '{assistant_response[:30]}...'")
    except Exception as e:
        log.error(f"Failed to log interaction to dataset: {e}")
