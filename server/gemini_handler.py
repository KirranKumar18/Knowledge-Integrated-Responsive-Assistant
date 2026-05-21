"""
gemini_handler.py — KIRA Phase 2: Gemini Fallback Module

This module handles all Gemini API interactions. It is the ONLY place
in the codebase that talks to Gemini. Key responsibilities:

1. Check if a Gemini API key is available
2. Detect when phi3:mini's response seems weak/uncertain
3. Send prompts to Gemini and return the response

Important constraints:
  - Never call Gemini without explicit user permission
  - This module only provides the tools — the permission gate is in server.py
  - API key comes from GEMINI_API_KEY environment variable
"""

import os
import re
import logging

log = logging.getLogger("kira-server")

# ---------------------------------------------------------------------------
# Gemini client setup
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# We lazy-load the client so the server still works without a key
_gemini_client = None


def _get_client():
    """Lazy-initialize the Gemini client. Returns None if no API key."""
    global _gemini_client

    if _gemini_client is not None:
        return _gemini_client

    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY not set — Gemini fallback is disabled")
        return None

    try:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        log.info(f"Gemini client initialized ✓ (model: {GEMINI_MODEL})")
        return _gemini_client
    except ImportError:
        log.error("google-genai package not installed. Run: pip install google-genai")
        return None
    except Exception as e:
        log.error(f"Failed to initialize Gemini client: {e}")
        return None


def is_gemini_available() -> bool:
    """Check if Gemini API is configured and ready."""
    return _get_client() is not None


# ---------------------------------------------------------------------------
# Complexity / uncertainty detection
# ---------------------------------------------------------------------------
# Phrases that suggest phi3:mini is struggling with the question
UNCERTAINTY_PHRASES = [
    r"i don'?t know",
    r"i('?m| am) not sure",
    r"i cannot",
    r"i can'?t",
    r"i('?m| am) unable",
    r"beyond my (capabilities|knowledge|ability)",
    r"i don'?t have (enough )?information",
    r"i('?m| am) not (the best|able|qualified)",
    r"you (should|might want to) (ask|check|consult|look)",
    r"i (would|can) (not|only) (provide|give|offer)",
    r"as an ai",
    r"as a language model",
    r"i lack the ability",
    r"this is (too )?complex",
    r"i (really )?struggle with",
]

# Pre-compile for speed
_uncertainty_patterns = [re.compile(p, re.IGNORECASE) for p in UNCERTAINTY_PHRASES]


def needs_gemini(response_text: str) -> bool:
    """
    Analyze phi3:mini's response to determine if Gemini should be offered.

    Returns True if the response shows signs of uncertainty or inadequacy.
    This does NOT trigger a Gemini call — it only suggests one.
    The actual permission comes from the user via the client.

    Detection strategy:
    1. Response is suspiciously short (< 15 chars) — likely a non-answer
    2. Response contains uncertainty/deflection phrases
    3. Response is mostly a refusal
    """
    if not is_gemini_available():
        return False  # no point suggesting Gemini if it's not configured

    text = response_text.strip()

    # Check 1: Suspiciously short response (but not empty — that's a different error)
    if 0 < len(text) < 15:
        log.info(f"Gemini suggested: response too short ({len(text)} chars)")
        return True

    # Check 2: Contains uncertainty phrases
    text_lower = text.lower()
    for pattern in _uncertainty_patterns:
        if pattern.search(text_lower):
            log.info(f"Gemini suggested: matched uncertainty pattern '{pattern.pattern}'")
            return True

    return False


# ---------------------------------------------------------------------------
# Gemini query
# ---------------------------------------------------------------------------
async def query_gemini(
    prompt: str,
    conversation_history: list[dict] | None = None,
) -> str | None:
    """
    Send a prompt to Gemini and return the response.

    Args:
        prompt: The user's question/request
        conversation_history: Optional list of {"role": "user"/"assistant", "content": "..."}

    Returns:
        The Gemini response text, or None if Gemini is unavailable/errored.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        # Build the full prompt with context
        full_prompt_parts = []

        # System instruction for KIRA personality
        system_instruction = (
            "You are KIRA, a personal AI voice assistant. "
            "You are the advanced brain — called upon for complex questions. "
            "Rules:\n"
            "1. Keep replies concise but thorough — 2-4 sentences max.\n"
            "2. No markdown formatting — your output is spoken aloud.\n"
            "3. Be helpful and direct. Give the actual answer, not filler.\n"
            "4. If conversation history is provided, use it for context."
        )

        # Include conversation history as context
        if conversation_history:
            context = "\n".join(
                f"{'User' if m['role'] == 'user' else 'KIRA'}: {m['content']}"
                for m in conversation_history[-6:]  # last 3 exchanges for context
            )
            full_prompt_parts.append(f"Previous conversation:\n{context}\n")

        full_prompt_parts.append(f"User's question: {prompt}")
        full_content = "\n".join(full_prompt_parts)

        # Call Gemini
        log.info(f"Querying Gemini ({GEMINI_MODEL})...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_content,
            config={
                "system_instruction": system_instruction,
                "max_output_tokens": 200,  # keep it concise for voice
                "temperature": 0.7,
            },
        )

        result = response.text.strip() if response.text else None
        if result:
            log.info(f"Gemini response: '{result[:80]}...'")
        return result

    except Exception as e:
        log.error(f"Gemini query failed: {e}")
        return None
