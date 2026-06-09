"""
visual_feedback.py — KIRA Phase 6
Handles terminal-based ANSI ASCII visual feedback animations for client states:
IDLE, LISTENING, PROCESSING, and SPEAKING.
"""

import sys
import time
import threading

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"
CLEAR_LINE = "\033[K"

class VisualFeedback:
    def __init__(self):
        self.state = "idle"  # idle, listening, processing, speaking, stopped
        self._thread = None
        self.is_running = False
        self._lock = threading.Lock()

    def set_state(self, state: str):
        """Update the visualizer state."""
        with self._lock:
            self.state = state.lower()

    def _render_loop(self):
        frame = 0
        
        # Audio wave frames for SPEAKING state
        wave_frames = [
            " ▃   ",
            " ▃▅  ",
            " ▃▅█ ",
            " ▃▅█▅",
            "  ▅█▅",
            "   █▅",
            "    ▅",
            "     "
        ]

        # Rotating spinners for PROCESSING state
        spinners = ["|", "/", "-", "\\"]

        # Pulsing bars for LISTENING state
        mic_bars = [
            "[=    ]",
            "[==   ]",
            "[===  ]",
            "[==== ]",
            "[=====]",
            "[ ====]",
            "[  ===]",
            "[   ==]",
            "[    =]",
            "[     ]"
        ]

        last_state = None
        while self.is_running:
            with self._lock:
                current_state = self.state

            if current_state == "stopped":
                break

            # 1. Idle state (Do not print background animations to avoid disrupting keyboard input)
            if current_state == "idle":
                if last_state != "idle":
                    sys.stdout.write(f"\r{CLEAR_LINE}")
                    sys.stdout.flush()
                last_state = "idle"
                time.sleep(0.1)
                continue

            last_state = current_state

            # 2. Listening state (Pulsing green wave)
            if current_state == "listening":
                bar = mic_bars[frame % len(mic_bars)]
                sys.stdout.write(f"\r{GREEN}{BOLD}🎙️  KIRA Listening {RESET}{GREEN}{bar}{RESET}{CLEAR_LINE}")
                sys.stdout.flush()
                time.sleep(0.12)

            # 3. Processing state (Yellow rotating spinner)
            elif current_state == "processing":
                spin = spinners[frame % len(spinners)]
                sys.stdout.write(f"\r{YELLOW}{BOLD}🧠 KIRA Thinking {RESET}{YELLOW}[ {spin} ]{RESET}{CLEAR_LINE}")
                sys.stdout.flush()
                time.sleep(0.1)

            # 4. Speaking state (Blue audio equalizer wave)
            elif current_state == "speaking":
                idx1 = frame % len(wave_frames)
                idx2 = (frame + 2) % len(wave_frames)
                idx3 = (frame + 4) % len(wave_frames)
                wave = f"{wave_frames[idx1]}{wave_frames[idx2]}{wave_frames[idx3]}"
                sys.stdout.write(f"\r{BLUE}{BOLD}🔊 KIRA Speaking {RESET}{BLUE}[{wave}]{RESET}{CLEAR_LINE}")
                sys.stdout.flush()
                time.sleep(0.1)

            frame += 1

        # Clear visualizer output on stop
        sys.stdout.write(f"\r{CLEAR_LINE}")
        sys.stdout.flush()

    def start(self):
        """Start the background visualizer thread."""
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the visualizer and join thread."""
        self.is_running = False
        self.set_state("stopped")
        if self._thread:
            self._thread.join(timeout=1.0)
        self._thread = None
