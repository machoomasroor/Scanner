from flask import Flask, request, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

DB_FILE = "licenses.json"

TRIAL_DAYS = 5
GLOBAL_BATCH = "DEFAULT"
GLOBAL_SERIAL = "TRIAL-KEY-0001"


# -------------------------------------------------------
# DATABASE HELPERS
# -------------------------------------------------------
def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


def ensure_structure(db):
    if GLOBAL_BATCH not in db:
        db[GLOBAL_BATCH] = {}
    if GLOBAL_SERIAL not in db[GLOBAL_BATCH]:
        db[GLOBAL_BATCH][GLOBAL_SERIAL] = {"machines": {}}
    if "machines" not in db[GLOBAL_BATCH][GLOBAL_SERIAL]:
        db[GLOBAL_BATCH][GLOBAL_SERIAL]["machines"] = {}
    return db


# -------------------------------------------------------
# LICENSE VALIDATION (5-DAY TRIAL PER MACHINE, GLOBAL KEY)
# -------------------------------------------------------
@app.route("/validate", methods=["POST"])
def validate():
    data = request.json or {}
    serial = data.get("serial")
    machine_id = data.get("machine_id")

    if not serial or not machine_id:
        return jsonify({"status": "error", "message": "serial and machine_id required"}), 400

    # Only one global key allowed
    if serial != GLOBAL_SERIAL:
        return jsonify({"status": "invalid"}), 403

    db = load_db()
    db = ensure_structure(db)

    machines = db[GLOBAL_BATCH][GLOBAL_SERIAL]["machines"]

    # First time this machine uses the key
    if machine_id not in machines:
        machines[machine_id] = {
            "activation_date": datetime.now().strftime("%Y-%m-%d")
        }
        save_db(db)
        return jsonify({"status": "activated", "days_left": TRIAL_DAYS})

    # Machine already exists → check expiration
    activation_date = datetime.strptime(
        machines[machine_id]["activation_date"], "%Y-%m-%d"
    )
    days_passed = (datetime.now() - activation_date).days
    days_left = TRIAL_DAYS - days_passed

    if days_left > 0:
        return jsonify({"status": "ok", "days_left": days_left})

    # Trial expired for this machine
    return jsonify({"status": "expired"}), 403


# -------------------------------------------------------
# ADMIN: KEY STATUS (PER-MACHINE TRIAL INFO)
# -------------------------------------------------------
@app.route("/admin/key_status", methods=["GET"])
def key_status():
    db = load_db()
    db = ensure_structure(db)

    machines = db[GLOBAL_BATCH][GLOBAL_SERIAL]["machines"]

    active_machines = []
    expired_machines = []

    for machine_id, record in machines.items():
        activation_date = datetime.strptime(record["activation_date"], "%Y-%m-%d")
        days_passed = (datetime.now() - activation_date).days
        days_left = TRIAL_DAYS - days_passed

        info = {
            "machine_id": machine_id,
            "activation_date": record["activation_date"],
            "days_passed": days_passed,
            "days_left": max(days_left, 0)
        }

        if days_left > 0:
            active_machines.append(info)
        else:
            expired_machines.append(info)

    return jsonify({
        "serial": GLOBAL_SERIAL,
        "total_machines": len(machines),
        "active_count": len(active_machines),
        "expired_count": len(expired_machines),
        "active_machines": active_machines,
        "expired_machines": expired_machines
    })


# -------------------------------------------------------
# ADMIN: SIMPLE STATS (COUNTS ONLY)
# -------------------------------------------------------
@app.route("/admin/stats", methods=["GET"])
def stats():
    db = load_db()
    db = ensure_structure(db)

    machines = db[GLOBAL_BATCH][GLOBAL_SERIAL]["machines"]

    total = len(machines)
    active = 0
    expired = 0

    for machine_id, record in machines.items():
        activation_date = datetime.strptime(record["activation_date"], "%Y-%m-%d")
        days_passed = (datetime.now() - activation_date).days
        days_left = TRIAL_DAYS - days_passed

        if days_left > 0:
            active += 1
        else:
            expired += 1

    return jsonify({
        "serial": GLOBAL_SERIAL,
        "trial_days": TRIAL_DAYS,
        "total_machines": total,
        "active_machines": active,
        "expired_machines": expired
    })


# -------------------------------------------------------
# HOME
# -------------------------------------------------------
@app.route("/")
def home():
    return "License server running (global 5-day trial per machine)"


# -------------------------------------------------------
# RUN
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
