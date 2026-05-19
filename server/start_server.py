"""
start_server.py — One-click launcher for the KIRA server

This script:
1. Checks that Ollama is running and phi3:mini is available
2. Starts the FastAPI server
3. Starts an ngrok tunnel (if ngrok is installed)
4. Prints the public URL for the phone client

Run: python start_server.py
"""

import subprocess
import sys
import time
import httpx


def check_ollama():
    """Verify Ollama is running and phi3:mini is downloaded."""
    print("🔍 Checking Ollama...")
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            print(f"   ✅ Ollama is running | Models: {', '.join(models)}")

            # Check if phi3:mini is available
            has_phi3 = any("phi3" in m for m in models)
            if not has_phi3:
                print("   ⚠️  phi3:mini not found. Pulling it now...")
                subprocess.run(["ollama", "pull", "phi3:mini"], check=True)
                print("   ✅ phi3:mini downloaded")
            return True
        else:
            print(f"   ❌ Ollama responded with {resp.status_code}")
            return False
    except httpx.ConnectError:
        print("   ❌ Ollama is not running")
        print("   Start it with: ollama serve")
        return False


def start_ngrok():
    """Start an ngrok tunnel on port 8000 and return the public URL."""
    print("\n🌐 Starting ngrok tunnel...")
    try:
        # Start ngrok in background
        proc = subprocess.Popen(
            ["ngrok", "http", "8000", "--log=stdout"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Give ngrok a moment to establish the tunnel
        time.sleep(3)

        # Get the public URL from ngrok's local API
        try:
            resp = httpx.get("http://localhost:4040/api/tunnels", timeout=5)
            tunnels = resp.json().get("tunnels", [])
            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    url = tunnel["public_url"]
                    print(f"   ✅ Ngrok tunnel: {url}")
                    print(f"\n   📱 On your phone, run:")
                    print(f"      python client.py --server {url}")
                    return url, proc
        except Exception:
            pass

        print("   ⚠️  Couldn't get ngrok URL automatically.")
        print("   Check http://localhost:4040 for the URL.")
        return None, proc

    except FileNotFoundError:
        print("   ⚠️  ngrok is not installed")
        print("   Install: https://ngrok.com/download")
        print("   Or use the server on local network: http://<laptop-ip>:8000")
        return None, None


def main():
    print("\n" + "=" * 50)
    print("  🤖 KIRA Server Launcher — Phase 1")
    print("=" * 50 + "\n")

    # Step 1: Check Ollama
    if not check_ollama():
        print("\n❌ Cannot start without Ollama. Exiting.")
        sys.exit(1)

    # Step 2: Start ngrok (optional but recommended)
    ngrok_url, ngrok_proc = start_ngrok()

    # Step 3: Start the FastAPI server
    print("\n🚀 Starting KIRA server on port 8000...")
    print("   Local:  http://localhost:8000")
    print("   Docs:   http://localhost:8000/docs")
    if ngrok_url:
        print(f"   Public: {ngrok_url}")
    print("\n   Press Ctrl+C to stop\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
            cwd=__import__("os").path.dirname(__import__("os").path.abspath(__file__)),
        )
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
    finally:
        if ngrok_proc:
            ngrok_proc.terminate()
            print("   Ngrok tunnel closed")
        print("   KIRA server stopped. Goodbye!")


if __name__ == "__main__":
    main()
