"""
offline.py — KIRA Phase 2: Offline Mode Inference Engine (Termux)

This module handles local AI inference on the phone when the laptop
server is unreachable (no WiFi, server down, etc.).

It uses llama-cpp (installed via pkg in Termux) to run a small GGUF
model directly on the phone's CPU.

Setup (run once on the phone):
  chmod +x setup_offline.sh && ./setup_offline.sh

How it works:
  - Calls llama-cli via subprocess (simpler and more reliable than Python bindings)
  - Uses a tiny model (Gemma 3 1B Q4_K_M ~800MB) that fits in 4GB RAM
  - Responses are much simpler than phi3:mini but enough for basics
  - Handles: schedule queries, timers, simple Q&A, small talk
"""

from __future__ import annotations

import os
import subprocess
import logging
import shutil

log = logging.getLogger("kira-client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Default model path — set by setup_offline.sh
MODEL_DIR = os.path.expanduser("~/kira-models")
DEFAULT_MODEL = os.path.join(MODEL_DIR, "qwen2.5-1.5b-instruct-q4_k_m.gguf")

# Generation settings — conservative for 4GB RAM phone
OFFLINE_MAX_TOKENS = 60       # very short responses
OFFLINE_TEMPERATURE = 0.7
OFFLINE_CONTEXT_SIZE = 2048   # small context to save RAM
OFFLINE_THREADS = 4           # most phones have 4-8 cores

# System prompt — stripped down for speed
OFFLINE_SYSTEM_PROMPT = (
    "You are KIRA, a simple voice assistant running in offline mode. "
    "Rules: Reply in ONE short sentence only. No lists, no markdown. "
    "Keep answers extremely brief — you are speaking out loud."
)


def _find_llama_cli() -> str | None:
    """Find the llama-cli binary. Checks common Termux install locations."""
    # Check if installed via pkg (most common)
    if shutil.which("llama-cli"):
        return "llama-cli"
    if shutil.which("llama"):
        return "llama"

    # Check if built from source
    search_dirs = [
        os.path.expanduser("~/llama.cpp/build/bin"),
        os.path.expanduser("~/llama.cpp/build"),
        os.path.expanduser("~/llama.cpp")
    ]
    
    # Check common explicit names first
    valid_names = ["llama-cli", "main", "llama"]
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        for name in valid_names:
            path = os.path.join(d, name)
            if os.path.exists(path):
                return path
                
        # Fallback: look for any executable ending in "-cli" (e.g. llama-qwen2vl-cli)
        try:
            for f in os.listdir(d):
                if f.endswith("-cli"):
                    path = os.path.join(d, f)
                    if os.path.exists(path):
                        return path
        except Exception:
            pass

    return None


def is_offline_available() -> bool:
    """
    Check if offline mode can work:
    1. llama-cli binary exists
    2. A GGUF model file exists
    """
    cli = _find_llama_cli()
    if cli is None:
        return False

    # Check for any .gguf file in the models directory
    if os.path.exists(DEFAULT_MODEL):
        return True

    # Check if any model exists in the directory
    if os.path.isdir(MODEL_DIR):
        for f in os.listdir(MODEL_DIR):
            if f.endswith(".gguf"):
                return True

    return False


def _get_model_path() -> str | None:
    """Get the path to the first available GGUF model."""
    if os.path.exists(DEFAULT_MODEL):
        return DEFAULT_MODEL

    if os.path.isdir(MODEL_DIR):
        for f in os.listdir(MODEL_DIR):
            if f.endswith(".gguf"):
                return os.path.join(MODEL_DIR, f)

    return None


def query_offline(prompt: str) -> str | None:
    """
    Run a prompt through the local GGUF model using llama-cli.

    Returns the model's response text, or None if offline inference fails.
    This is intentionally simple — just call the CLI and parse output.
    """
    cli = _find_llama_cli()
    model = _get_model_path()

    if not cli or not model:
        return None

    # Build the full prompt with system instruction
    full_prompt = f"<start_of_turn>user\n{OFFLINE_SYSTEM_PROMPT}\n\n{prompt}<end_of_turn>\n<start_of_turn>model\n"

    try:
        result = subprocess.run(
            [
                cli,
                "-m", model,
                "-p", full_prompt,
                "-n", str(OFFLINE_MAX_TOKENS),
                "-t", str(OFFLINE_THREADS),
                "-c", str(OFFLINE_CONTEXT_SIZE),
                "--temp", str(OFFLINE_TEMPERATURE),
                "--no-display-prompt",   # don't echo the prompt back
                "--log-disable",         # suppress llama.cpp logs
            ],
            capture_output=True,
            text=True,
            timeout=60,  # 60 second timeout — small models on phone can be slow
        )

        if result.returncode != 0:
            log.error(f"llama-cli failed: {result.stderr[:200]}")
            return None

        # Parse the output — llama-cli prints the generated text to stdout
        response = result.stdout.strip()

        # Clean up common artifacts from the model output
        # Remove any trailing special tokens
        for token in ["<end_of_turn>", "<eos>", "</s>", "<|end|>", "<|endoftext|>"]:
            if token in response:
                response = response.split(token)[0].strip()

        if response:
            log.info(f"[offline] Response: '{response[:80]}...'")
            return response
        else:
            return "I'm in offline mode and couldn't generate a response. Try again?"

    except subprocess.TimeoutExpired:
        log.error("Offline model timed out (60s)")
        return "Sorry, I'm thinking too slowly in offline mode. Try a simpler question?"

    except FileNotFoundError:
        log.error(f"llama-cli not found at: {cli}")
        return None

    except Exception as e:
        log.error(f"Offline inference error: {e}")
        return None


def get_offline_status() -> dict:
    """Return status info about offline mode setup."""
    cli = _find_llama_cli()
    model = _get_model_path()

    return {
        "available": is_offline_available(),
        "llama_cli": cli or "not found",
        "model": os.path.basename(model) if model else "not found",
        "model_path": model or "N/A",
        "max_tokens": OFFLINE_MAX_TOKENS,
        "threads": OFFLINE_THREADS,
    }
