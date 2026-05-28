"""
load_monitor.py — KIRA Phase 3
Tracks server load, active requests, engine states, and execution history.
"""

import time
import logging
import threading
from collections import deque
from datetime import datetime
import psutil

log = logging.getLogger("kira-server.load_monitor")

class LoadMonitor:
    def __init__(self):
        self.active_requests = 0
        self.whisper_active = False
        self.ollama_active = False
        self.gemini_active = False
        
        # Keep last 50 requests
        self.history = deque(maxlen=50)
        self._lock = threading.Lock()
        
        # Global counts
        self.total_requests = 0
        self.total_failures = 0
        
        # Performance history lists for averages (capped at 100 entries)
        self.whisper_times = []
        self.ollama_times = []
        self.gemini_times = []
        self.total_times = []

    def get_stats(self) -> dict:
        """Retrieves current system load and AI metrics in a thread-safe manner."""
        with self._lock:
            avg_whisper = sum(self.whisper_times) / len(self.whisper_times) if self.whisper_times else 0
            avg_ollama = sum(self.ollama_times) / len(self.ollama_times) if self.ollama_times else 0
            avg_gemini = sum(self.gemini_times) / len(self.gemini_times) if self.gemini_times else 0
            avg_total = sum(self.total_times) / len(self.total_times) if self.total_times else 0
            
            # Fetch system metrics
            try:
                # interval=None gets non-blocking CPU usage since last call (or system startup)
                cpu_percent = psutil.cpu_percent()
                memory_percent = psutil.virtual_memory().percent
                cpu_count = psutil.cpu_count()
            except Exception as e:
                log.warning(f"Failed to read system metrics: {e}")
                cpu_percent = 0.0
                memory_percent = 0.0
                cpu_count = 1

            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory_percent,
                    "cpu_count": cpu_count,
                },
                "status": {
                    "active_requests": self.active_requests,
                    "whisper_active": self.whisper_active,
                    "ollama_active": self.ollama_active,
                    "gemini_active": self.gemini_active,
                },
                "averages": {
                    "whisper_seconds": round(avg_whisper, 2),
                    "ollama_seconds": round(avg_ollama, 2),
                    "gemini_seconds": round(avg_gemini, 2),
                    "total_seconds": round(avg_total, 2),
                },
                "totals": {
                    "requests": self.total_requests,
                    "failures": self.total_failures,
                },
                "history": list(self.history)
            }

    def add_history_entry(self, entry: dict):
        """Adds a request execution entry to history and updates averages."""
        with self._lock:
            # Add to history list
            self.history.appendleft(entry)
            
            # Increment totals
            self.total_requests += 1
            if entry.get("status") != "success":
                self.total_failures += 1
                
            # Add times to running list for averages, keeping capacity capped
            w_time = entry.get("whisper_time", 0)
            if w_time and w_time > 0:
                self.whisper_times.append(w_time)
                if len(self.whisper_times) > 100:
                    self.whisper_times.pop(0)

            o_time = entry.get("ollama_time", 0)
            if o_time and o_time > 0:
                self.ollama_times.append(o_time)
                if len(self.ollama_times) > 100:
                    self.ollama_times.pop(0)

            g_time = entry.get("gemini_time", 0)
            if g_time and g_time > 0:
                self.gemini_times.append(g_time)
                if len(self.gemini_times) > 100:
                    self.gemini_times.pop(0)

            t_time = entry.get("total_time", 0)
            if t_time and t_time > 0:
                self.total_times.append(t_time)
                if len(self.total_times) > 100:
                    self.total_times.pop(0)

# Global monitor instance
load_monitor = LoadMonitor()
