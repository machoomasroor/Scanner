import requests
import json
import time
import threading
from datetime import datetime
from fastapi import FastAPI

# ============================
# CONFIG
# ============================
SERVER_VALIDATE = "https://license-server-3ciz.onrender.com"   # Server A (real validation)
SERVER_PING = "https://license-server-1-o9cg.onrender.com"      # Server B (keep alive)

SERIAL_KEY = "PLAN30-TEST-0001"
MACHINE_ID = "machine1"

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
        print("\n==============================================")
        print("CHECK TIME:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("==============================================")

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

        print("\nSleeping 60 seconds...\n")
        time.sleep(60)

# ============================
# START BACKGROUND THREAD
# ============================
threading.Thread(target=background_loop, daemon=True).start()

# ============================
# WEB ENDPOINT (Render needs this)
# ============================
@app.get("/")
def home():
    return {"status": "running", "message": "Validation + KeepAlive loop active"}
