import requests
import json
import time
import threading
from datetime import datetime
from fastapi import FastAPI

# ============================
# CONFIG — TWO RENDER SERVERS
# ============================
SERVERS = [
    "https://license-server-3ciz.onrender.com",
    "https://license-server-1-o9cg.onrender.com"
]

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

# ============================
# VALIDATION LOOP
# ============================
def validation_loop():
    while True:
        print("\n==============================================")
        print("CHECK TIME:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("==============================================")

        payload = {
            "serial": SERIAL_KEY,
            "machine_id": MACHINE_ID
        }

        for server in SERVERS:
            srv, status, data = post(server, "/validate", payload)
            print(f"\n--- Server: {srv} ---")
            print("Status:", status)
            print(json.dumps(data, indent=4, default=str))

        print("\nSleeping 60 seconds...\n")
        time.sleep(60)

# ============================
# START BACKGROUND THREAD
# ============================
threading.Thread(target=validation_loop, daemon=True).start()

# ============================
# WEB ENDPOINT (Render needs this)
# ============================
@app.get("/")
def home():
    return {"status": "running", "message": "Validation loop active"}
