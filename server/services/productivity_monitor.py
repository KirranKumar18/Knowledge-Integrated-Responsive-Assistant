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

# ANSI color codes for terminal output
YELLOW = "\033[93m"
RESET = "\033[0m"

# Keywords that indicate a distracting window
DISTRACTING_KEYWORDS = ["YouTube", "Twitter", "X", "Instagram", "Reddit", "Facebook", "Netflix","whatsapp"]

# How long (in seconds) the user is allowed to be distracted before KIRA intervenes
DISTRACTION_THRESHOLD = 10  # 5 minute

class ProductivityMonitor:
    def __init__(self):
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self.current_distraction_time = 0
        self.last_check_time = 0
        self.pending_alerts = []
        self._lock = threading.Lock()

    def _check_window(self):
        if not gw:
            log.warning("pygetwindow not installed. Productivity monitor disabled.")
            return

        window = gw.getActiveWindow()
        if not window:
            return

        title = window.title
        
        # Check if the title contains any distracting keywords
        is_distracted = False
        import re
        for keyword in DISTRACTING_KEYWORDS:
            kw_lower = keyword.lower()
            title_lower = title.lower()
            if kw_lower == 'x':
                # Match 'x' as a standalone word (e.g. "on X") or "x.com"
                if re.search(r'\bx\b|\bx\.com\b', title_lower):
                    is_distracted = True
                    break
            elif kw_lower in title_lower:
                is_distracted = True
                break
        
        now = time.time()
        elapsed = now - self.last_check_time if self.last_check_time > 0 else 0
        self.last_check_time = now

        if is_distracted:
            self.current_distraction_time += elapsed
        #    log.info(f"{YELLOW}[Monitor]{RESET} Distraction detected: '{title}'. Total time: {int(self.current_distraction_time)}s")
            
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
        log.warning(f"{YELLOW}[Monitor] 🚨 PRODUCTIVITY ALERT:{RESET} You have been distracted by '{title}' for too long!")
        
        # Check if queue already contains an alert to prevent spam backup
        with self._lock:
            if len(self.pending_alerts) > 0:
                log.info("[Monitor] Alert skipped because an alert is already pending in the queue.")
                return

        app_name = "distractions"
        for keyword in DISTRACTING_KEYWORDS:
            if keyword.lower() in title.lower():
                app_name = keyword
                break
        
        if app_name.lower() == "whatsapp":
            app_name = "WhatsApp"
        elif app_name.lower() == "youtube":
            app_name = "YouTube"
        else:
            app_name = app_name.capitalize()

        message = f"Hey! You've been distracted by {app_name} for too long. Let's get back to work!"
        with self._lock:
            self.pending_alerts.append(message)

    def get_and_clear_alerts(self):
        """Thread-safe retrieval and clearing of pending alerts."""
        with self._lock:
            alerts = list(self.pending_alerts)
            self.pending_alerts.clear()
        return alerts

    def _monitor_loop(self):
        self.last_check_time = time.time()
        while self.is_running:
            try:
                self._check_window()
            except Exception as e:
                log.error(f"Error checking window: {e}")
            time.sleep(2)  # Check every 2 seconds

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        log.info(f"{YELLOW}[Monitor]{RESET} Productivity monitor started in the background.")

    def stop(self):
        self.is_running = False
        if self._thread:
            self._thread.join(timeout=2)
            
# Global instance
monitor = ProductivityMonitor()
