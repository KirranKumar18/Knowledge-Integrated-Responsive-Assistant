"""
services/ — KIRA server background services.

Contains long-running processes like the productivity monitor.
"""

from .productivity_monitor import monitor
