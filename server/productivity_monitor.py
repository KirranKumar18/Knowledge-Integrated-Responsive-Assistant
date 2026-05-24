"""
productivity_monitor.py — KIRA Phase 3
Tracks active window usage and logs productivity vs distraction.
"""

import time
import logging
import threading
from typing import Optional

try:
    import pygetwindow as gw
except ImportError:
    gw = None

log = logging.getLogger("kira-server.productivity")

# Keywords that indicate a distracting window
DISTRACTING_KEYWORDS = ["YouTube", "Twitter", "X", "Instagram", "Reddit", "Facebook", "Netflix"]

# How long (in seconds) the user is allowed to be distracted before KIRA intervenes
DISTRACTION_THRESHOLD = 300  # 5 minutes

class ProductivityMonitor:
    def __init__(self):
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.current_distraction_time = 0
        self.last_check_time = 0

    def _check_window(self):
        if not gw:
            log.warning("pygetwindow not installed. Productivity monitor disabled.")
            return

        window = gw.getActiveWindow()
        if not window:
            return

        title = window.title
        
        # Check if the title contains any distracting keywords
        is_distracted = any(keyword.lower() in title.lower() for keyword in DISTRACTING_KEYWORDS)
        
        now = time.time()
        elapsed = now - self.last_check_time if self.last_check_time > 0 else 0
        self.last_check_time = now

        if is_distracted:
            self.current_distraction_time += elapsed
            log.info(f"[Monitor] Distraction detected: '{title}'. Total time: {int(self.current_distraction_time)}s")
            
            if self.current_distraction_time >= DISTRACTION_THRESHOLD:
                self._trigger_intervention(title)
                # Reset after intervention so we don't spam
                self.current_distraction_time = 0
        else:
            # If they switch to a productive window, slowly cool down the distraction timer
            # or just reset it. For simplicity, we reset it if they are productive for 10 seconds.
            if self.current_distraction_time > 0:
                self.current_distraction_time -= elapsed * 2
                if self.current_distraction_time < 0:
                    self.current_distraction_time = 0

    def _trigger_intervention(self, title: str):
        """Called when distraction threshold is reached."""
        log.warning(f"🚨 PRODUCTIVITY ALERT: You have been distracted by '{title}' for too long!")
        # TODO: Integrate with KIRA's voice to actually speak to the user

    def _monitor_loop(self):
        self.last_check_time = time.time()
        while self.is_running:
            try:
                self._check_window()
            except Exception as e:
                log.error(f"Error checking window: {e}")
            time.sleep(5)  # Check every 5 seconds

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log.info("Productivity monitor started in the background.")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
            
# Global instance
monitor = ProductivityMonitor()
