"""
load_monitor.py — KIRA Phase 3
Tracks server load, active requests, engine states, and execution history.
Includes background GPU/iGPU monitoring via Windows CIM/DirectX registry.
"""

import time
import logging
import threading
import json
import subprocess
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

        # GPU metrics
        self.gpu_percent = 0.0
        self.igpu_percent = 0.0
        self.gpu_name = "dGPU"
        self.igpu_name = "iGPU"
        self._is_running = True
        
        # Start background GPU monitoring thread
        self._gpu_thread = threading.Thread(target=self._poll_gpu_loop, daemon=True)
        self._gpu_thread.start()

    def _poll_gpu_loop(self):
        """Polls Windows CIM / Registry for GPU and iGPU utilization in the background."""
        while self._is_running:
            try:
                # Query LUID mapping and GPUEngine counters via a single fast PowerShell command
                cmd = [
                    "powershell", "-NoProfile", "-Command",
                    "$l = Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\DirectX\\*' -ErrorAction SilentlyContinue | Select-Object Description, AdapterLuid; "
                    "$g = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | Where-Object {$_.Name -like '*_3D'} | Select-Object Name, UtilizationPercentage; "
                    "[PSCustomObject]@{ LuidMap=$l; GPUEngines=$g } | ConvertTo-Json -Depth 3"
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if res.returncode == 0 and res.stdout.strip():
                    payload = json.loads(res.stdout.strip())
                    
                    # 1. Parse LUID Map
                    luid_map = {}
                    luid_items = payload.get("LuidMap", [])
                    if isinstance(luid_items, dict):
                        luid_items = [luid_items]
                    
                    for item in luid_items:
                        desc = item.get("Description", "")
                        luid_val = item.get("AdapterLuid")
                        if desc and luid_val is not None:
                            # Hex format with 8 digits after 0x, e.g. "0x000107EF"
                            hex_str = f"0x{luid_val:08x}".upper().replace("0X", "0x")
                            luid_map[hex_str] = desc

                    # Update friendly names
                    for luid, desc in luid_map.items():
                        desc_lower = desc.lower()
                        if "nvidia" in desc_lower or "rtx" in desc_lower or "geforce" in desc_lower or "radeon" in desc_lower:
                            if "intel" not in desc_lower:
                                self.gpu_name = desc
                        elif "intel" in desc_lower or "amd" in desc_lower or "integrated" in desc_lower:
                            self.igpu_name = desc

                    # 2. Sum Utilization by LUID
                    gpu_engines = payload.get("GPUEngines", [])
                    if isinstance(gpu_engines, dict):
                        gpu_engines = [gpu_engines]
                        
                    luid_utils = {}
                    for eng in gpu_engines:
                        name = eng.get("Name", "")
                        util = eng.get("UtilizationPercentage", 0)
                        
                        # Extract the LUID portion from Name (e.g. pid_13164_luid_0x00000000_0x000107EF_phys_0_...)
                        parts = name.split("_")
                        if "luid" in parts:
                            idx = parts.index("luid")
                            if idx + 2 < len(parts):
                                low_luid = parts[idx + 2]
                                try:
                                    normalized_luid = f"0x{int(low_luid, 16):08x}".upper().replace("0X", "0x")
                                    luid_utils[normalized_luid] = luid_utils.get(normalized_luid, 0) + util
                                except Exception:
                                    pass

                    # 3. Map aggregates to iGPU and dGPU
                    temp_gpu = 0.0
                    temp_igpu = 0.0
                    for luid, util in luid_utils.items():
                        desc = luid_map.get(luid, "")
                        if desc:
                            desc_lower = desc.lower()
                            if "nvidia" in desc_lower or "rtx" in desc_lower or "geforce" in desc_lower:
                                temp_gpu = max(temp_gpu, util)
                            elif "intel" in desc_lower or "uhd" in desc_lower or "iris" in desc_lower or "integrated" in desc_lower:
                                temp_igpu = max(temp_igpu, util)
                            else:
                                if "basic render" not in desc_lower:
                                    temp_igpu = max(temp_igpu, util)
                        else:
                            # Fallback based on typical hex patterns
                            if "10BCD" in luid.upper():
                                temp_gpu = max(temp_gpu, util)
                            elif "107EF" in luid.upper():
                                temp_igpu = max(temp_igpu, util)

                    with self._lock:
                        self.gpu_percent = min(100.0, float(temp_gpu))
                        self.igpu_percent = min(100.0, float(temp_igpu))

            except Exception as e:
                log.debug(f"GPU polling failed: {e}")
            
            time.sleep(2.0)

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
                    "gpu_percent": self.gpu_percent,
                    "igpu_percent": self.igpu_percent,
                    "gpu_name": self.gpu_name,
                    "igpu_name": self.igpu_name
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

    def stop(self):
        """Stops the background GPU polling thread."""
        self._is_running = False

# Global monitor instance
load_monitor = LoadMonitor()
