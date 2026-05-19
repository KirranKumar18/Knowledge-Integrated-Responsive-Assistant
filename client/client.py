"""
client.py — KIRA Phase 1: Phone-side Voice Client (Termux)

This script runs on your Android phone inside Termux. It does:
1. Records your voice using Termux:API microphone
2. Sends the audio to the KIRA server on your laptop
3. Receives the AI response text
4. Speaks the response using Termux:API TTS

Prerequisites on phone (run these in Termux):
  pkg install python termux-api
  pip install requests

Usage:
  python client.py                          # uses saved/default server URL
  python client.py --server https://xxxx.ngrok.io  # specify server URL
"""

from __future__ import annotations  # enables dict | None syntax on Python < 3.10

import os
import sys
import json
import time
import subprocess
import argparse
import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG_FILE = os.path.expanduser("~/.kira_config.json")
DEFAULT_SERVER = "http://localhost:8000"  # will be overridden with ngrok URL

RECORDING_FILE = os.path.expanduser("~/kira_recording.m4a")  # .m4a = AAC in 3GP container, ffmpeg-compatible
RECORDING_DURATION = 5  # seconds — how long to listen
RECORDING_SAMPLE_RATE = 44100  # 44.1kHz — standard for AAC


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
def termux_tts_speak(text: str):
    """
    Speak text aloud using Termux:API TTS engine.
    This uses the Android system TTS (Google TTS usually).
    """
    try:
        subprocess.run(
            ["termux-tts-speak", text],
            timeout=60,
            check=True,
        )
    except FileNotFoundError:
        print(f"[TTS fallback] {text}")
        print("(Install termux-api package: pkg install termux-api)")
    except subprocess.TimeoutExpired:
        print("[TTS] Speech timed out")


def termux_record_audio(output_path: str, duration: int = RECORDING_DURATION):
    """
    Record audio from the microphone using Termux:API.
    Records for `duration` seconds and saves to `output_path`.
    """
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
# Server communication
# ---------------------------------------------------------------------------
def check_server(server_url: str) -> bool:
    """Ping the server health endpoint to verify connectivity."""
    try:
        resp = requests.get(f"{server_url}/health", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Server online | Model: {data.get('model')} | Ollama: {data.get('ollama')}")
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


def send_voice(server_url: str, audio_path: str) -> dict | None:
    """
    Send recorded audio to the KIRA server's /voice endpoint.
    Returns the parsed JSON response or None on failure.
    """
    try:
        with open(audio_path, "rb") as f:
            files = {"audio": (os.path.basename(audio_path), f)}
            print("📡 Sending to KIRA server...")
            resp = requests.post(
                f"{server_url}/voice",
                files=files,
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


def send_text(server_url: str, message: str) -> dict | None:
    """
    Send text to the KIRA server's /chat endpoint (for testing).
    Returns the parsed JSON response or None on failure.
    """
    try:
        resp = requests.post(
            f"{server_url}/chat",
            json={"message": message},
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


# ---------------------------------------------------------------------------
# Main conversation loop
# ---------------------------------------------------------------------------
def conversation_loop(server_url: str, text_mode: bool = False):
    """
    The main loop:
    1. Record voice (or get text input in text mode)
    2. Send to server
    3. Speak response
    4. Repeat
    """
    print("\n" + "=" * 50)
    print("  🤖 KIRA is ready")
    print("  Say something or press Ctrl+C to exit")
    if text_mode:
        print("  [Text mode — type your messages]")
    print("=" * 50)

    termux_toast("KIRA is ready")
    termux_tts_speak("KIRA is online and ready.")

    while True:
        try:
            if text_mode:
                # Text input mode — for testing without microphone
                message = input("\nYou: ").strip()
                if not message:
                    continue
                if message.lower() in ("exit", "quit", "bye"):
                    termux_tts_speak("Goodbye!")
                    print("👋 KIRA signing off.")
                    break

                result = send_text(server_url, message)

            else:
                # Voice mode — the real deal
                print("\n" + "-" * 30)
                input("Press Enter to speak (or Ctrl+C to exit)...")
                termux_vibrate(150)  # haptic feedback: I'm listening

                if not termux_record_audio(RECORDING_FILE):
                    print("Try again...")
                    continue

                result = send_voice(server_url, RECORDING_FILE)

            # Process the response
            if result:
                transcription = result.get("transcription")
                response = result.get("response", "")

                if transcription:
                    print(f"\n📝 You said: {transcription}")

                print(f"\n🤖 KIRA: {response}")

                # Speak the response aloud
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

    print("\n🤖 KIRA — Phase 1 Voice Client")
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

    # Check server connectivity
    print("\n🔍 Checking server connection...")
    if not check_server(server_url):
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
