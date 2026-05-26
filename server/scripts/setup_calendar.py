"""
setup_calendar.py -- One-time Google Calendar OAuth setup for KIRA

Run this ONCE to authenticate with Google Calendar.
It will open a browser window where you log in with your Google account
and grant KIRA permission to read/write calendar events.

After success, a token.json file is created and KIRA can use your calendar.

Usage:
    python setup_calendar.py
"""

import os
import sys
from pathlib import Path

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add the server directory to path (parent of scripts/)
sys.path.insert(0, str(Path(__file__).parent.parent))

from handlers.calendar_handler import get_calendar_service, get_schedule

def main():
    print("=" * 50)
    print("  KIRA -- Google Calendar Setup")
    print("=" * 50)
    print()
    print("This will open a browser window for Google login.")
    print("Grant KIRA access to your Google Calendar.")
    print()
    
    # Check if credentials.json exists
    config_dir = Path(__file__).parent.parent / "config"
    creds_path = config_dir / "credentials.json"
    token_path = config_dir / "token.json"
    
    if not creds_path.exists():
        print("[ERROR] credentials.json not found!")
        print("   Place your Google Cloud OAuth credentials file here:")
        print(f"   {creds_path}")
        sys.exit(1)
    
    print("[OK] credentials.json found")
    
    if token_path.exists():
        print("[INFO] token.json already exists -- will try to use existing auth")
    else:
        print("[INFO] token.json not found -- will start OAuth flow")
    
    print()
    print("[AUTH] Starting authentication... A browser window should open.")
    print()
    
    # This will trigger the OAuth flow if needed
    service = get_calendar_service()
    
    if service is None:
        print()
        print("[ERROR] Authentication failed!")
        print("   Check the error messages above.")
        sys.exit(1)
    
    # Verify it works by fetching the schedule
    print()
    print("[OK] Authentication successful! token.json created.")
    print()
    print("[TEST] Fetching your upcoming events...")
    print()
    
    schedule = get_schedule()
    print(f"   {schedule}")
    
    print()
    print("=" * 50)
    print("  [DONE] Calendar setup complete!")
    print("  KIRA can now read and create calendar events.")
    print("  Restart the server for changes to take effect.")
    print("=" * 50)


if __name__ == "__main__":
    main()
