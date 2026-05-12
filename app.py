from flask import Flask, request, jsonify
import json
import os
from datetime import datetime, timedelta

app = Flask(__name__)

DB_FILE = "licenses.json"
BANNED_MACHINES_FILE = "banned_machines.json"

# Default trial settings
DEFAULT_TRIAL_DAYS = 5
DEFAULT_MAX_MACHINES_PER_SERIAL = 999999990  # unlimited machines per trial key


# -------------------------------------------------------
# DATABASE HELPERS
# -------------------------------------------------------
def load_db():
    if not os.path.exists(DB_FILE):
        return {"serials": {}}
    try:
        with open(DB_FILE, "r") as f:
            return json.load(f)
    except:
        return {"serials": {}}


def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)


def ensure_serial_entry(db, serial):
    if serial not in db["serials"]:
        db["serials"][serial] = {
            "created_at": datetime.utcnow().isoformat(),
            "trial_days": DEFAULT_TRIAL_DAYS,
            "max_machines": DEFAULT_MAX_MACHINES_PER_SERIAL,
            "machines": {}
        }
    return db


# -------------------------------------------------------
# BANNED MACHINE HELPERS
# -------------------------------------------------------
def load_banned():
    if not os.path.exists(BANNED_MACHINES_FILE):
        return []
    try:
        with open(BANNED_MACHINES_FILE, "r") as f:
            return json.load(f)
    except:
        return []


def save_banned(banned):
    with open(BANNED_MACHINES_FILE, "w") as f:
        json.dump(banned, f, indent=4)


# -------------------------------------------------------
# UTILS
# -------------------------------------------------------
def utc_now():
    return datetime.utcnow()


def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


# REAL FIX: return days + hours + minutes
def compute_remaining_time(activation_ts: datetime, trial_days: int):
    now = utc_now()
    delta = now - activation_ts

    total_minutes_passed = int(delta.total_seconds() // 60)
    trial_minutes = trial_days * 24 * 60

    remaining_minutes = trial_minutes - total_minutes_passed

    if remaining_minutes <= 0:
        return 0, 0, 0, True

    days_left = remaining_minutes // 1440
    hours_left = (remaining_minutes % 1440) // 60
    minutes_left = remaining_minutes % 60

    return int(days_left), int(hours_left), int(minutes_left), False


# -------------------------------------------------------
# STRICT TRIAL VALIDATION
# -------------------------------------------------------
@app.route("/validate", methods=["POST"])
def validate():
    data = request.json or {}
    serial = data.get("serial")
    machine_id = data.get("machine_id")

    if not serial or not machine_id:
        return jsonify({"status": "error", "message": "serial and machine_id required"}), 400

    banned = load_banned()
    if machine_id in banned:
        return jsonify({"status": "expired", "reason": "machine_banned"}), 403

    db = load_db()
    db = ensure_serial_entry(db, serial)

    serial_entry = db["serials"][serial]
    trial_days = serial_entry.get("trial_days", DEFAULT_TRIAL_DAYS)
    max_machines = serial_entry.get("max_machines", DEFAULT_MAX_MACHINES_PER_SERIAL)
    machines = serial_entry["machines"]

    now = utc_now()

    # ---------------------------------------------------
    # 1) Machine already exists
    # ---------------------------------------------------
    if machine_id in machines:
        record = machines[machine_id]

        if record.get("expired", False):
            if machine_id not in banned:
                banned.append(machine_id)
                save_banned(banned)
            return jsonify({"status": "expired"}), 403

        # Anti-tamper
        last_seen_str = record.get("last_seen")
        if last_seen_str:
            try:
                last_seen = parse_iso(last_seen_str)
                if now < last_seen - timedelta(minutes=5):
                    record["expired"] = True
                    record["reason"] = "time_tamper"
                    save_db(db)

                    if machine_id not in banned:
                        banned.append(machine_id)
                        save_banned(banned)

                    return jsonify({"status": "expired", "reason": "time_tamper"}), 403
            except:
                pass

        activation_ts = parse_iso(record["activation_timestamp"])
        days_left, hours_left, minutes_left, is_expired = compute_remaining_time(activation_ts, trial_days)

        record["last_seen"] = now.isoformat()

        if not is_expired:
            save_db(db)
            return jsonify({
                "status": "ok",
                "days_left": days_left,
                "hours_left": hours_left,
                "minutes_left": minutes_left
            })

        # Trial expired
        record["expired"] = True
        record["reason"] = "trial_ended"
        save_db(db)

        if machine_id not in banned:
            banned.append(machine_id)
            save_banned(banned)

        return jsonify({"status": "expired"}), 403

    # ---------------------------------------------------
    # 2) New machine activation
    # ---------------------------------------------------
    active_machines_count = sum(
        1 for rec in machines.values() if not rec.get("expired", False)
    )

    if active_machines_count >= max_machines:
        return jsonify({"status": "denied", "message": "max_machines_reached"}), 403

    activation_ts = now
    days_left, hours_left, minutes_left, is_expired = compute_remaining_time(activation_ts, trial_days)

    machines[machine_id] = {
        "activation_timestamp": activation_ts.isoformat(),
        "last_seen": now.isoformat(),
        "expired": False,
        "reason": None,
    }
    save_db(db)

    if is_expired:
        machines[machine_id]["expired"] = True
        machines[machine_id]["reason"] = "trial_ended"
        save_db(db)

        if machine_id not in banned:
            banned.append(machine_id)
            save_banned(banned)

        return jsonify({"status": "expired"}), 403

    return jsonify({
        "status": "activated",
        "days_left": days_left,
        "hours_left": hours_left,
        "minutes_left": minutes_left
    })


# -------------------------------------------------------
# ADMIN: SERIAL STATUS
# -------------------------------------------------------
@app.route("/admin/serial_status/<serial>", methods=["GET"])
def serial_status(serial):
    db = load_db()
    if serial not in db["serials"]:
        return jsonify({"error": "serial_not_found"}), 404

    serial_entry = db["serials"][serial]
    trial_days = serial_entry.get("trial_days", DEFAULT_TRIAL_DAYS)
    machines = serial_entry.get("machines", {})

    active = []
    expired = []

    for machine_id, record in machines.items():
        activation_ts = parse_iso(record["activation_timestamp"])
        days_left, hours_left, minutes_left, is_expired = compute_remaining_time(activation_ts, trial_days)

        expired_flag = record.get("expired", False) or is_expired

        info = {
            "machine_id": machine_id,
            "activation_timestamp": record["activation_timestamp"],
            "last_seen": record.get("last_seen"),
            "days_left": days_left,
            "hours_left": hours_left,
            "minutes_left": minutes_left,
            "expired": expired_flag,
            "reason": record.get("reason"),
        }

        if expired_flag:
            expired.append(info)
        else:
            active.append(info)

    return jsonify({
        "serial": serial,
        "active_machines": active,
        "expired_machines": expired,
    })


# -------------------------------------------------------
# ADMIN: GLOBAL STATS
# -------------------------------------------------------
@app.route("/admin/stats", methods=["GET"])
def stats():
    db = load_db()
    serials = db.get("serials", {})

    total_serials = len(serials)
    total_machines = 0
    total_active = 0
    total_expired = 0

    for serial, serial_entry in serials.items():
        trial_days = serial_entry.get("trial_days", DEFAULT_TRIAL_DAYS)
        machines = serial_entry.get("machines", {})

        for machine_id, record in machines.items():
            total_machines += 1
            activation_ts = parse_iso(record["activation_timestamp"])
            days_left, hours_left, minutes_left, is_expired = compute_remaining_time(activation_ts, trial_days)
            expired_flag = record.get("expired", False) or is_expired
            if expired_flag:
                total_expired += 1
            else:
                total_active += 1

    return jsonify({
        "total_serials": total_serials,
        "total_machines": total_machines,
        "active_machines": total_active,
        "expired_machines": total_expired,
    })


# -------------------------------------------------------
# ADMIN: DOWNLOAD DATABASE
# -------------------------------------------------------
@app.route("/licenses.json", methods=["GET"])
def download_db():
    if not os.path.exists(DB_FILE):
        return jsonify({"serials": {}})
    with open(DB_FILE, "r") as f:
        return jsonify(json.load(f))


# -------------------------------------------------------
# HOME
# -------------------------------------------------------
@app.route("/")
def home():
    return "Strict 5-day trial server with permanent machine ban running"


# -------------------------------------------------------
# RUN
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
