"""
client.py — KIRA Phase 2: Phone-side Voice Client (Termux)

This script runs on your Android phone inside Termux. It does:
1. Records your voice using Termux:API microphone
2. Sends the audio to the KIRA server on your laptop
3. Receives the AI response text
4. Speaks the response using gTTS
5. [Phase 2] Maintains conversation sessions across turns
6. [Phase 2] Handles Gemini permission gate — asks before using Gemini
7. [Phase 2] Switches to offline mode when server is unreachable

Prerequisites on phone (run these in Termux):
  pkg install python termux-api
  pip install requests gTTS

Usage:
  python client.py                          # uses saved/default server URL
  python client.py --server https://xxxx.ngrok.io  # specify server URL
  python client.py --text                   # text mode (no microphone)
"""

from __future__ import annotations  # enables dict | None syntax on Python < 3.10

import os
import sys
import json
import time
import uuid
import threading
import subprocess
import argparse
import requests

# Phase 2: Import offline inference engine
try:
    from offline import query_offline, is_offline_available, get_offline_status
    OFFLINE_SUPPORTED = True
except ImportError:
    OFFLINE_SUPPORTED = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG_FILE = os.path.expanduser("~/.kira_config.json")
DEFAULT_SERVER = "http://localhost:8000"  # will be overridden with ngrok URL

RECORDING_FILE = os.path.expanduser("~/kira_recording.m4a")  # .m4a = AAC in 3GP container, ffmpeg-compatible
RECORDING_DURATION = 3  # seconds — how long to listen
RECORDING_SAMPLE_RATE = 44100  # 44.1kHz — standard for AAC

# Phase 2: Connectivity check settings
HEALTH_CHECK_TIMEOUT = 3  # seconds — quick ping to detect online/offline
GEMINI_CONFIRM_WORDS = {"yes", "yeah", "yep", "sure", "go ahead", "do it", "okay", "ok"}


# ---------------------------------------------------------------------------
# Config persistence — remembers your server URL between runs
# ---------------------------------------------------------------------------
def load_config() -> dict:
    """Load saved config from disk."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config: dict):
    """Save config to disk."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


# ---------------------------------------------------------------------------
# Termux helpers — wrapping Termux:API commands
# ---------------------------------------------------------------------------
_tts_proc: subprocess.Popen | None = None  # tracks current TTS process so we can kill it


def stop_tts():
    """Immediately kill any ongoing TTS speech (called before recording)."""
    global _tts_proc
    if _tts_proc and _tts_proc.poll() is None:
        _tts_proc.kill()  # Aggressive kill so it stops instantly
    _tts_proc = None
    
    # Stop termux native player if it's playing
    try:
        subprocess.run(["termux-media-player", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def termux_tts_speak(text: str, block: bool = False):
    """
    Speak text aloud using gTTS (Google's neural voice).
    Requires: pip install gTTS && pkg install mpv
    """
    global _tts_proc

    def _speak():
        global _tts_proc

        try:
            from gtts import gTTS
            tts = gTTS(text=text, lang='en', tld='com') # tld='com' for standard US, 'co.uk' for British etc
            
            # Save to a temporary file
            audio_file = os.path.expanduser("~/kira_response.mp3")
            tts.save(audio_file)
            
            # Try to play with SoX (play) to increase speed in real-time
            # tempo 1.25 makes it 25% faster without changing pitch
            try:
                _tts_proc = subprocess.Popen(
                    ["play", "-q", audio_file, "tempo", "2.5"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except FileNotFoundError:
                # Fallback to normal speed if SoX isn't installed
                _tts_proc = subprocess.Popen(
                    ["termux-media-player", "play", audio_file],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            
            _tts_proc = None
            return

        except Exception as e:
            # Fallback if gTTS or mpv fails
            print(f"\n[KIRA said] {text}")
            print(f"  (TTS failed: {e})")
            _tts_proc = None

    if block:
        _speak()
    else:
        t = threading.Thread(target=_speak, daemon=True)
        t.start()




def termux_record_audio(output_path: str, duration: int = RECORDING_DURATION):
    """
    Record audio from the microphone using Termux:API.
    Records for `duration` seconds and saves to `output_path`.
    """
    # Delete stale file first — prevents old recording from being sent if this one fails
    if os.path.exists(output_path):
        os.remove(output_path)

    print(f"\n🎙️  Listening for {duration} seconds...")

    try:
        # Start recording in background
        record_proc = subprocess.Popen(
            [
                "termux-microphone-record",
                "-f", output_path,
                "-l", str(duration),
                "-e", "aac",    # AAC encoder → proper .m4a/3GP file, ffmpeg-compatible
                "-r", str(RECORDING_SAMPLE_RATE),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for recording duration + small buffer
        time.sleep(duration + 1)

        # Stop recording
        subprocess.run(
            ["termux-microphone-record", "-q"],
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        record_proc.wait(timeout=5)
        time.sleep(0.8)  # give mic time to fully release before next recording

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            size_kb = os.path.getsize(output_path) / 1024
            print(f"✅ Recorded ({size_kb:.1f} KB)")
            return True
        else:
            print("❌ Recording failed — empty file")
            return False

    except FileNotFoundError:
        print("❌ termux-microphone-record not found")
        print("   Install it: pkg install termux-api")
        return False
    except Exception as e:
        print(f"❌ Recording error: {e}")
        return False


def termux_vibrate(duration_ms: int = 100):
    """Quick vibration to signal KIRA is listening."""
    try:
        subprocess.run(
            ["termux-vibrate", "-d", str(duration_ms)],
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # vibration is optional, don't crash


def termux_toast(text: str):
    """Show a brief toast notification on screen."""
    try:
        subprocess.run(
            ["termux-toast", text],
            timeout=5,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Phase 2: Connectivity detection
# ---------------------------------------------------------------------------
def is_server_reachable(server_url: str) -> bool:
    """
    Quick health check — determines online vs offline mode.
    Uses a short timeout so switching is fast.
    """
    try:
        resp = requests.get(f"{server_url}/health", timeout=HEALTH_CHECK_TIMEOUT)
        return resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        return False


# ---------------------------------------------------------------------------
# Server communication
# ---------------------------------------------------------------------------
def check_server(server_url: str) -> bool:
    """Ping the server health endpoint to verify connectivity (startup check)."""
    try:
        resp = requests.get(f"{server_url}/health", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Server online | Model: {data.get('model')} | Ollama: {data.get('ollama')}")
            # Phase 2: Show additional info
            if data.get("gemini_available"):
                print(f"   Gemini: available")
            if data.get("active_sessions", 0) > 0:
                print(f"   Active sessions: {data.get('active_sessions')}")
            return True
        else:
            print(f"❌ Server returned status {resp.status_code}")
            return False
    except requests.ConnectionError:
        print(f"❌ Cannot connect to {server_url}")
        return False
    except requests.Timeout:
        print(f"❌ Connection timed out: {server_url}")
        return False


def send_voice(server_url: str, audio_path: str, session_id: str | None = None) -> dict | None:
    """
    Send recorded audio to the KIRA server's /voice endpoint.
    Returns the parsed JSON response or None on failure.
    """
    try:
        with open(audio_path, "rb") as f:
            files = {"audio": (os.path.basename(audio_path), f)}
            # Phase 2: include session_id as form data
            data = {}
            if session_id:
                data["session_id"] = session_id

            print("📡 Sending to KIRA server...")
            resp = requests.post(
                f"{server_url}/voice",
                files=files,
                data=data,
                timeout=120,  # Whisper + Ollama can take a moment
            )

        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ Server error ({resp.status_code}): {resp.text[:200]}")
            return None

    except requests.ConnectionError:
        print("❌ Lost connection to server")
        return None
    except requests.Timeout:
        print("❌ Request timed out (model may be overloaded)")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def send_text(server_url: str, message: str, session_id: str | None = None) -> dict | None:
    """
    Send text to the KIRA server's /chat endpoint (for testing).
    Returns the parsed JSON response or None on failure.
    """
    try:
        payload = {"message": message}
        if session_id:
            payload["session_id"] = session_id

        resp = requests.post(
            f"{server_url}/chat",
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ Server error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def request_gemini(server_url: str, prompt: str, session_id: str | None = None) -> dict | None:
    """
    Phase 2: Send a user-approved prompt to the Gemini endpoint.
    Called ONLY after the user explicitly says "yes" to the permission prompt.
    """
    try:
        payload = {"prompt": prompt}
        if session_id:
            payload["session_id"] = session_id

        print("🧠 Asking Gemini...")
        resp = requests.post(
            f"{server_url}/gemini",
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"❌ Gemini error ({resp.status_code}): {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Gemini error: {e}")
        return None


# ---------------------------------------------------------------------------
# Phase 2: Gemini permission gate — asks user before calling Gemini
# ---------------------------------------------------------------------------
def handle_gemini_permission(
    server_url: str,
    original_prompt: str,
    phi3_response: str,
    session_id: str | None,
    text_mode: bool,
) -> str | None:
    """
    Handle the Gemini permission flow:
    1. Speak "I'm not fully confident. Should I check with Gemini?"
    2. Wait for user confirmation
    3. If yes → call /gemini and return upgraded response
    4. If no → return None (caller will use original phi3 response)
    """
    # Announce to the user
    prompt_text = "I'm not fully confident in that answer. Want me to check with Gemini?"
    print(f"\n💡 KIRA: {prompt_text}")
    termux_tts_speak(prompt_text, block=True)

    if text_mode:
        # Text mode: simple input
        user_input = input("\nYou (yes/no): ").strip().lower()
        confirmed = user_input in GEMINI_CONFIRM_WORDS
    else:
        # Voice mode: record and check for confirmation
        print("\n🎙️  Say 'yes' or 'no'...")
        termux_vibrate(100)

        if not termux_record_audio(RECORDING_FILE, duration=2):
            print("   Didn't catch that — sticking with the original answer.")
            return None

        # Send the short recording to the server for transcription
        # We use the /voice endpoint but only care about the transcription
        confirm_result = send_voice(server_url, RECORDING_FILE, session_id=None)
        if not confirm_result:
            return None

        user_words = (confirm_result.get("transcription", "") or "").lower().strip()
        print(f"   You said: '{user_words}'")

        # Check if any confirmation word appears in the transcription
        confirmed = any(word in user_words for word in GEMINI_CONFIRM_WORDS)

    if confirmed:
        gemini_result = request_gemini(server_url, original_prompt, session_id)
        if gemini_result:
            return gemini_result.get("response")
        else:
            print("   Gemini didn't work — using the original answer.")
            return None
    else:
        print("   Okay, sticking with the original answer.")
        return None


# ---------------------------------------------------------------------------
# Phase 2: Offline mode handler
# ---------------------------------------------------------------------------
def handle_offline_turn(prompt: str) -> str | None:
    """
    Handle a single conversation turn in offline mode.
    Uses the local GGUF model via llama-cli.
    """
    if not OFFLINE_SUPPORTED or not is_offline_available():
        return "I'm offline and don't have a local model set up. Please reconnect to the server."

    print("🔌 [Offline mode] Processing locally...")
    response = query_offline(prompt)
    return response


# ---------------------------------------------------------------------------
# Main conversation loop
# ---------------------------------------------------------------------------
def conversation_loop(server_url: str, text_mode: bool = False):
    """
    The main loop:
    1. Check connectivity → online or offline mode
    2. Record voice (or get text input in text mode)
    3. Send to server (online) or process locally (offline)
    4. Handle Gemini permission gate if suggested
    5. Speak response
    6. Repeat
    """
    # Phase 2: Generate a session ID for conversation memory
    session_id = str(uuid.uuid4())
    mode = "online"  # "online" or "offline"

    print("\n" + "=" * 50)
    print("  🤖 KIRA is ready")
    print(f"  Session: {session_id[:8]}...")
    print("  Say something or press Ctrl+C to exit")
    if text_mode:
        print("  [Text mode — type your messages]")
    if OFFLINE_SUPPORTED and is_offline_available():
        print("  [Offline mode available ✓]")
    print("=" * 50)

    termux_toast("KIRA is ready")
    termux_tts_speak("KIRA is online and ready.")

    while True:
        try:
            # Phase 2: Check connectivity at the start of each turn
            server_reachable = is_server_reachable(server_url)

            # Handle mode transitions
            if mode == "online" and not server_reachable:
                mode = "offline"
                switch_msg = "I've lost connection to the server. Switching to offline mode."
                print(f"\n⚡ {switch_msg}")
                termux_tts_speak(switch_msg)

            elif mode == "offline" and server_reachable:
                mode = "online"
                switch_msg = "Server is back online. Switching to full mode."
                print(f"\n⚡ {switch_msg}")
                termux_tts_speak(switch_msg)
                # Start a new session since the server doesn't have the old one
                session_id = str(uuid.uuid4())

            # ── Get user input ──────────────────────────────────────────

            if text_mode:
                mode_tag = "offline" if mode == "offline" else "online"
                message = input(f"\nYou [{mode_tag}]: ").strip()
                if not message:
                    continue
                if message.lower() in ("exit", "quit", "bye"):
                    termux_tts_speak("Goodbye!")
                    print("👋 KIRA signing off.")
                    break
                # Phase 2: "new" or "new conversation" → reset session
                if message.lower() in ("new", "new conversation", "reset", "forget"):
                    session_id = str(uuid.uuid4())
                    print(f"🔄 New session: {session_id[:8]}...")
                    termux_tts_speak("Starting a fresh conversation.")
                    continue

                user_prompt = message
                result = None

                if mode == "online":
                    result = send_text(server_url, message, session_id)
                else:
                    # Offline: process locally
                    offline_response = handle_offline_turn(message)
                    if offline_response:
                        result = {"response": offline_response, "model": "offline"}

            else:
                # Voice mode — the real deal
                print("\n" + "-" * 30)
                input("Press Enter to speak (or Ctrl+C to exit)...")
                stop_tts()       # ← kill KIRA's speech so mic doesn't pick it up
                termux_vibrate(150)  # haptic feedback: I'm listening

                if not termux_record_audio(RECORDING_FILE):
                    print("Try again...")
                    continue

                user_prompt = None  # will be set from transcription

                if mode == "online":
                    result = send_voice(server_url, RECORDING_FILE, session_id)
                    if result:
                        user_prompt = result.get("transcription")
                else:
                    # Offline: we can't easily transcribe locally (no Whisper on phone)
                    # For now, fall back to text input in offline voice mode
                    print("⚠️  Voice transcription requires the server.")
                    print("   Type your message instead:")
                    user_prompt = input("   You: ").strip()
                    if not user_prompt:
                        continue
                    offline_response = handle_offline_turn(user_prompt)
                    if offline_response:
                        result = {"response": offline_response, "model": "offline"}
                    else:
                        result = None

            # ── Process the response ────────────────────────────────────

            if result:
                transcription = result.get("transcription")
                response = result.get("response", "")

                if transcription:
                    print(f"\n📝 You said: {transcription}")

                print(f"\n🤖 KIRA: {response}")

                # Phase 2: Check if Gemini was suggested
                if result.get("gemini_suggested") and mode == "online":
                    # Show the phi3 response first
                    termux_tts_speak(response, block=True)

                    # Ask for Gemini permission
                    prompt_for_gemini = user_prompt or transcription or ""
                    gemini_response = handle_gemini_permission(
                        server_url, prompt_for_gemini, response, session_id, text_mode
                    )

                    if gemini_response:
                        print(f"\n🧠 KIRA (Gemini): {gemini_response}")
                        termux_tts_speak(gemini_response)
                    # else: user declined or Gemini failed, original response already spoken
                else:
                    # Normal response — speak it
                    termux_tts_speak(response)
            else:
                termux_tts_speak("Sorry, I couldn't process that.")

        except KeyboardInterrupt:
            print("\n\n👋 KIRA signing off.")
            termux_tts_speak("Goodbye!")
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="KIRA Voice Client (Termux)")
    parser.add_argument(
        "--server",
        type=str,
        help="Server URL (e.g., https://xxxx.ngrok.io)",
    )
    parser.add_argument(
        "--text",
        action="store_true",
        help="Use text input instead of voice (for testing)",
    )
    args = parser.parse_args()

    print("\n🤖 KIRA — Phase 2 Voice Client")
    print("=" * 40)

    # Determine server URL: CLI arg > saved config > default
    config = load_config()

    if args.server:
        server_url = args.server.rstrip("/")
        config["server_url"] = server_url
        save_config(config)
        print(f"📌 Server URL saved: {server_url}")
    elif "server_url" in config:
        server_url = config["server_url"]
        print(f"📌 Using saved server: {server_url}")
    else:
        server_url = DEFAULT_SERVER
        print(f"📌 Using default server: {server_url}")

    # Phase 2: Show offline mode status
    if OFFLINE_SUPPORTED:
        status = get_offline_status()
        if status["available"]:
            print(f"🔌 Offline mode: ready ({status['model']})")
        else:
            print("🔌 Offline mode: not set up (run setup_offline.sh)")
    else:
        print("🔌 Offline mode: not available (offline.py not found)")

    # Check server connectivity
    print("\n🔍 Checking server connection...")
    if not check_server(server_url):
        # Phase 2: If server is down but offline mode is available, continue
        if OFFLINE_SUPPORTED and is_offline_available():
            print("\n⚠️  Server is not reachable, but offline mode is available.")
            print("   Starting in offline mode...")
        else:
            print("\n⚠️  Server is not reachable.")
            print("   Make sure:")
            print("   1. server.py is running on your laptop")
            print("   2. Ngrok tunnel is active")
            print(f"   3. URL is correct: {server_url}")

            retry = input("\nRetry? (y/n): ").strip().lower()
            if retry != "y":
                sys.exit(1)

            if not check_server(server_url):
                print("❌ Still can't connect. Exiting.")
                sys.exit(1)

    # Start the conversation loop
    conversation_loop(server_url, text_mode=args.text)


if __name__ == "__main__":
    main()
