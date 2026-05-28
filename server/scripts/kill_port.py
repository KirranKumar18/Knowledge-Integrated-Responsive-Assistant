import subprocess
import re
import sys

def free_port(port: int):
    try:
        # Find process using the port
        print(f"[Search] Searching for process on port {port}...")
        result = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        
        if not result.stdout.strip():
            print(f"[OK] Port {port} is already free!")
            return

        # Extract PID (last column in netstat output)
        lines = result.stdout.strip().split("\n")
        pid_to_kill = None
        for line in lines:
            if f":{port}" in line and "LISTENING" in line:
                pid_to_kill = line.split()[-1]
                break
        if not pid_to_kill:
            # Fallback if LISTENING isn't found
            pid_to_kill = lines[0].split()[-1]

        # Kill the process
        print(f"[Kill] Found stuck process (PID: {pid_to_kill}). Killing it...")
        subprocess.run(f"taskkill /PID {pid_to_kill} /F", shell=True)
        print("[OK] Port successfully freed!")

    except Exception as e:
        print(f"[Error] Error: {e}")

if __name__ == "__main__":
    free_port(8000)
