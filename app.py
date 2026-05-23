import requests
import json
import time
from datetime import datetime

# ============================
# CONFIG — TWO RENDER SERVERS
# ============================
SERVERS = [
    "https://license-server-3ciz.onrender.com",   # Render Server A
    "https://license-server-1-o9cg.onrender.com"  # Render Server B
]

SERIAL_KEY = "PLAN30-TEST-0001"
MACHINE_ID = "machine1"


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
# VALIDATE BOTH SERVERS
# ============================
def validate_both_servers():
    payload = {
        "serial": SERIAL_KEY,
        "machine_id": MACHINE_ID
    }

    print("\n==============================")
    print(" VALIDATING BOTH SERVERS ")
    print("==============================")

    for server in SERVERS:
        srv, status, data = post(server, "/validate", payload)
        print(f"\n--- Server: {srv} ---")
        print("Status:", status)
        print(json.dumps(data, indent=4, default=str))


# ============================
# CONTINUOUS VALIDATION LOOP
# ============================
if __name__ == "__main__":
    print("Starting continuous validation loop (every 60 seconds)...")

    try:
        while True:
            print("\n==============================================")
            print("CHECK TIME:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            print("==============================================")

            validate_both_servers()

            print("\nSleeping 60 seconds...\n")
            time.sleep(60)

    except KeyboardInterrupt:
        print("\nStopped by user.")
