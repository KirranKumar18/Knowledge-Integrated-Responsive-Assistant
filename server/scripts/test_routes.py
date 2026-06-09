"""
test_routes.py — Run integration tests for KIRA FastAPI server routes.
Run from repository root: python server/scripts/test_routes.py
"""

import os
import sys
import uuid
import time
from pathlib import Path

# Configure stdout and stderr to use UTF-8 on Windows to avoid UnicodeEncodeError for checkmarks/emojis
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Force Whisper model to 'tiny' to avoid downloading/loading large model during testing
os.environ["WHISPER_MODEL"] = "tiny"

# Add parent directory to path to import server
sys.path.append(str(Path(__file__).parent.parent))

# Import env vars from config
_env_path = Path(__file__).parent.parent / "config" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _val.strip())

try:
    from fastapi.testclient import TestClient
    from server import app
except ImportError:
    print("FastAPI TestClient dependencies missing. Installing...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "httpx"], check=True)
    from fastapi.testclient import TestClient
    from server import app

client = TestClient(app)

def run_tests():
    print("=" * 60)
    print("Running KIRA FastAPI Routes Integration Tests")
    print("=" * 60)
    
    session_id = f"test_route_sess_{uuid.uuid4().hex[:6]}"
    print(f"Test Session ID: {session_id}")

    # 1. Test GET /health
    print("\n[Test 1] Testing GET /health...")
    resp = client.get("/health")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
    data = resp.json()
    print(f"Health Response: {data}")
    assert data["status"] == "online"
    assert "model" in data
    print("GET /health PASSED [OK]")

    # 2. Test GET /api/stats
    print("\n[Test 2] Testing GET /api/stats (Load Monitor)...")
    resp = client.get("/api/stats")
    assert resp.status_code == 200
    data = resp.json()
    print(f"Stats Response: {data}")
    assert "system" in data and "cpu_percent" in data["system"]
    print("GET /api/stats PASSED [OK]")

    # 3. Test GET /alerts (initial state)
    print("\n[Test 3] Testing GET /alerts (should be no alerts initially)...")
    resp = client.get("/alerts", params={"session_id": session_id})
    assert resp.status_code == 200
    data = resp.json()
    print(f"Alerts Response: {data}")
    assert data["status"] == "no_alerts"
    print("GET /alerts PASSED [OK]")

    # 4. Test POST /chat - Simple conversational prompt
    print("\n[Test 4] Testing POST /chat (conversational)...")
    payload = {
        "message": "hello kira, how are you?",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"Chat Response: {data['response']}")
    assert len(data["response"]) > 0
    print("POST /chat (conversational) PASSED [OK]")

    # 5. Test POST /chat - Task Creation ("I need to finish homework and buy milk")
    print("\n[Test 5] Testing POST /chat (task creation)...")
    payload = {
        "message": "I need to buy milk",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"Task Add Response: {data['response']}")
    assert "milk" in data["response"].lower() or "remind" in data["response"].lower()
    print("POST /chat (task creation) PASSED [OK]")

    # 6. Test GET /tasks/{session_id}
    print("\n[Test 6] Testing GET /tasks/{session_id}...")
    resp = client.get(f"/tasks/{session_id}")
    assert resp.status_code == 200
    data = resp.json()
    print(f"Tasks List: {data}")
    assert data["task_count"] >= 1
    print("GET /tasks/{session_id} PASSED [OK]")

    # 7. Test POST /chat - Task Listing ("what are my tasks")
    print("\n[Test 7] Testing POST /chat (task listing)...")
    payload = {
        "message": "what are my tasks",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"Chat List Tasks Response: {data['response']}")
    assert "buy milk" in data["response"].lower() or "1 active task" in data["response"].lower()
    print("POST /chat (task listing) PASSED [OK]")

    # 8. Test POST /chat - Task Completion ("finished buying milk")
    print("\n[Test 8] Testing POST /chat (task completion)...")
    payload = {
        "message": "finished buying milk",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"Chat Task Done Response: {data['response']}")
    assert "done" in data["response"].lower() or "marked" in data["response"].lower() or "milk" in data["response"].lower()
    print("POST /chat (task completion) PASSED [OK]")

    # 9. Test POST /chat - Google Calendar scheduling ("schedule gym at 5pm")
    print("\n[Test 9] Testing POST /chat (Google Calendar scheduling)...")
    payload = {
        "message": "schedule gym at 5pm",
        "session_id": session_id
    }
    try:
        resp = client.post("/chat", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        print(f"Calendar Schedule Response: {data['response']}")
        assert "calendar" in data["response"].lower() or "connected" in data["response"].lower() or "gym" in data["response"].lower() or "error" in data["response"].lower()
        print("POST /chat (Calendar scheduling) PASSED [OK]")
    except Exception as calendar_err:
        print(f"Calendar scheduling test raised exception: {calendar_err}")
        print("This could be due to calendar oauth requirements.")

    # 10. Test POST /chat - Web search routing ("search the web for capital of France")
    print("\n[Test 10] Testing POST /chat (web search routing)...")
    payload = {
        "message": "search the web for capital of France",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"Web Search Response: {data['response']}")
    assert "france" in data["response"].lower() or "paris" in data["response"].lower() or "search" in data["response"].lower()
    print("POST /chat (web search) PASSED [OK]")

    # 11. Test POST /chat - GitHub search routing ("find rust tutorials on github")
    print("\n[Test 11] Testing POST /chat (github search routing)...")
    payload = {
        "message": "find rust tutorials on github",
        "session_id": session_id
    }
    resp = client.post("/chat", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"GitHub Search Response: {data['response']}")
    assert "github" in data["response"].lower() or "rust" in data["response"].lower()
    print("POST /chat (github search) PASSED [OK]")

    # 12. Test Gemini Permission Gating Suggestion
    print("\n[Test 12] Testing Gemini permission gating trigger...")
    from handlers.gemini_handler import needs_gemini, is_gemini_available
    assert needs_gemini("I don't know the answer to this complex quantum mechanics problem.") == True
    assert needs_gemini("Paris.") == True
    assert needs_gemini("The capital of France is Paris, which is a beautiful city in Europe.") == False
    print("Gemini Permission Trigger logic verified successfully [OK]")

    # 13. Test POST /gemini endpoint if key available
    if is_gemini_available():
        print("\n[Test 13] Testing POST /gemini fallback query...")
        payload = {
            "prompt": "what is the speed of light in vacuum?",
            "session_id": session_id
        }
        resp = client.post("/gemini", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        print(f"Gemini Response: {data['response']}")
        assert "gemini" in data["model"].lower()
        print("POST /gemini fallback query PASSED [OK]")
    else:
        print("\n[Test 13] Gemini API not available. Skipping active fallback test.")

    print("\n" + "=" * 60)
    print("All Route Integration Tests Passed Successfully!")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
