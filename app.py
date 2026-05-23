import requests
import json
import time
import threading
import os
from datetime import datetime
from fastapi import FastAPI

# ============================
# CONFIG
# ============================
SERVER_VALIDATE = "https://license-server-3ciz.onrender.com"   # Server A (real validation)
SERVER_PING = "https://license-server-1-o9cg.onrender.com"      # Server B (keep alive)

# Set YOUR own Render service URL here so the service can ping itself to stay awake
# Example: "https://license-server-1-o9cg.onrender.com"
SELF_URL = os.environ.get("SELF_URL", "")

SERIAL_KEY = "PLAN30-TEST-0001"
MACHINE_ID = "machine1"

INTERVAL_SECONDS = 60

app = FastAPI()

# ============================
# API CALL HELPER
# ============================
def post(server, endpoint, payload):
    url = f"{server}{endpoint}"
    try:
        r = requests.post(url, json=payload, timeout=50)
        return server, r.status_code, r.json()
    except Exception as e:
        return server, None, {"error": str(e)}

def get(server):
    url = f"{server}/"
    try:
        r = requests.get(url, timeout=20)
        return server, r.status_code, r.text
    except Exception as e:
        return server, None, str(e)

# ============================
# BACKGROUND LOOP
# ============================
def background_loop():
    while True:
        try:
            print("\n==============================================")
            print("CHECK TIME:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("==============================================")

            # ---- SELF-PING to prevent Render free tier spin-down ----
            if SELF_URL:
                try:
                    requests.get(SELF_URL, timeout=10)
                    print("Self-ping OK:", SELF_URL)
                except Exception as e:
                    print("Self-ping failed (non-fatal):", str(e))

            # ---- VALIDATE ON SERVER A ----
            payload = {
                "serial": SERIAL_KEY,
                "machine_id": MACHINE_ID
            }

            print("\n--- VALIDATING ON SERVER A ---")
            srv, status, data = post(SERVER_VALIDATE, "/validate", payload)
            print("Server:", srv)
            print("Status:", status)
            print(json.dumps(data, indent=4, default=str))

            # ---- PING SERVER B TO KEEP ALIVE ----
            print("\n--- PINGING SERVER B (KEEP ALIVE) ---")
            srv, status, data = get(SERVER_PING)
            print("Server:", srv)
            print("Status:", status)
            print("Response:", data)

        except Exception as e:
            # Catch ALL exceptions so the loop never dies silently
            print("\n!!! LOOP ERROR (will retry in 60s) !!!")
            print(str(e))

        print(f"\nSleeping {INTERVAL_SECONDS} seconds...\n")
        time.sleep(INTERVAL_SECONDS)


def start_background_thread():
    t = threading.Thread(target=background_loop, daemon=True)
    t.start()
    return t

# ============================
# WATCHDOG — restarts thread if it ever dies
# ============================
def watchdog():
    t = start_background_thread()
    while True:
        time.sleep(30)
        if not t.is_alive():
            print("!!! Background thread died — restarting !!!")
            t = start_background_thread()

threading.Thread(target=watchdog, daemon=True).start()

# ============================
# WEB ENDPOINTS (Render needs this)
# ============================
@app.get("/")
def home():
    return {"status": "running", "message": "Validation + KeepAlive loop active"}

@app.head("/")
def home_head():
    return {}

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

@app.head("/health")
def health_head():
    return {}
