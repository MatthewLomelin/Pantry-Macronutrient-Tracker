# app.py
# Simple Macro & Pantry Tracker
# Run with:
#   python app.py
# Then open http://127.0.0.1:5000 in your browser.
#
# Data is stored in a local SQLite file (pantry.db).

from flask import Flask, request, jsonify, send_from_directory, render_template
import sqlite3
from datetime import datetime, date

app = Flask(__name__, static_folder="static", template_folder="templates")

DB_PATH = "pantry.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    # Pantry items: per-unit macros allow flexible quantities
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pantry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            unit TEXT NOT NULL DEFAULT 'g',
            calories_per_unit REAL NOT NULL DEFAULT 0,
            protein_per_unit  REAL NOT NULL DEFAULT 0,
            carbs_per_unit    REAL NOT NULL DEFAULT 0,
            fat_per_unit      REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    # Daily targets (store last-set targets, and we compute per-day summaries separately)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS macros_targets (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            calories REAL NOT NULL DEFAULT 0,
            protein REAL NOT NULL DEFAULT 0,
            carbs   REAL NOT NULL DEFAULT 0,
            fat     REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    # Consumption logs (food diary). We store absolute macros for each action.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS consumption_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_date TEXT NOT NULL,
            item_id INTEGER,
            item_name TEXT NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            calories REAL NOT NULL,
            protein REAL NOT NULL,
            carbs REAL NOT NULL,
            fat REAL NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (item_id) REFERENCES pantry(id)
        )
    """)
    conn.commit()
    # Ensure there is always a row for targets id=1
    cur.execute("SELECT 1 FROM macros_targets WHERE id = 1")
    if cur.fetchone() is None:
        now = datetime.utcnow().isoformat()
        cur.execute("""INSERT INTO macros_targets (id, calories, protein, carbs, fat, updated_at)
                       VALUES (1, 0, 0, 0, 0, ?)""", (now,))
        conn.commit()
    conn.close()

@app.route("/")
def index_page():
    return render_template("index.html")

@app.route("/api/pantry", methods=["GET"])
def list_pantry():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pantry ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/api/pantry", methods=["POST"])
def add_pantry():
    data = request.get_json(force=True)
    required = ["name", "quantity", "unit", "calories_per_unit", "protein_per_unit", "carbs_per_unit", "fat_per_unit"]
    for key in required:
        if key not in data:
            return jsonify({"error": f"Missing field: {key}"}), 400
    conn = get_db()
    cur = conn.cursor()
    now = datetime.utcnow().isoformat()
    cur.execute("""INSERT INTO pantry (name, quantity, unit, calories_per_unit, protein_per_unit, carbs_per_unit, fat_per_unit, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["name"].strip(),
                 float(data["quantity"]),
                 data["unit"].strip(),
                 float(data["calories_per_unit"]),
                 float(data["protein_per_unit"]),
                 float(data["carbs_per_unit"]),
                 float(data["fat_per_unit"]),
                 now))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id}), 201

@app.route("/api/pantry/<int:item_id>", methods=["PUT"])
def update_pantry(item_id):
    data = request.get_json(force=True)
    allowed = ["name", "quantity", "unit", "calories_per_unit", "protein_per_unit", "carbs_per_unit", "fat_per_unit"]
    fields = []
    values = []
    for k in allowed:
        if k in data:
            fields.append(f"{k} = ?")
            values.append(data[k])
    if not fields:
        return jsonify({"error": "No fields to update"}), 400
    values.append(item_id)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"UPDATE pantry SET {', '.join(fields)} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/pantry/<int:item_id>", methods=["DELETE"])
def delete_pantry(item_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pantry WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/consume", methods=["POST"])
def consume():
    data = request.get_json(force=True)
    required = ["item_id", "quantity"]
    for key in required:
        if key not in data:
            return jsonify({"error": f"Missing field: {key}"}), 400
    qty = float(data["quantity"])
    if qty <= 0:
        return jsonify({"error": "Quantity must be > 0"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM pantry WHERE id = ?", (data["item_id"],))
    item = cur.fetchone()
    if not item:
        conn.close()
        return jsonify({"error": "Item not found"}), 404

    # Calculate macros for the consumed quantity
    calories = item["calories_per_unit"] * qty
    protein  = item["protein_per_unit"]  * qty
    carbs    = item["carbs_per_unit"]    * qty
    fat      = item["fat_per_unit"]      * qty

    # Reduce pantry quantity (can't go below zero)
    new_qty = max(0.0, item["quantity"] - qty)
    cur.execute("UPDATE pantry SET quantity = ? WHERE id = ?", (new_qty, item["id"]))

    # Insert into log
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    cur.execute("""INSERT INTO consumption_log
        (log_date, item_id, item_name, quantity, unit, calories, protein, carbs, fat, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (today, item["id"], item["name"], qty, item["unit"], calories, protein, carbs, fat, data.get("note", ""), now))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/logs", methods=["GET"])
def get_logs():
    qdate = request.args.get("date") or date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM consumption_log WHERE log_date = ? ORDER BY created_at DESC", (qdate,))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route("/api/macros/targets", methods=["GET"])
def get_targets():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT calories, protein, carbs, fat, updated_at FROM macros_targets WHERE id = 1")
    row = cur.fetchone()
    conn.close()
    return jsonify(dict(row))

@app.route("/api/macros/targets", methods=["POST"])
def set_targets():
    data = request.get_json(force=True)
    for key in ["calories", "protein", "carbs", "fat"]:
        if key not in data:
            return jsonify({"error": f"Missing field: {key}"}), 400
    now = datetime.utcnow().isoformat()
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""UPDATE macros_targets
                   SET calories = ?, protein = ?, carbs = ?, fat = ?, updated_at = ?
                   WHERE id = 1""",
                (float(data["calories"]), float(data["protein"]), float(data["carbs"]), float(data["fat"]), now))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/macros/summary", methods=["GET"])
def macros_summary():
    qdate = request.args.get("date") or date.today().isoformat()
    conn = get_db()
    cur = conn.cursor()
    # Get targets
    cur.execute("SELECT calories, protein, carbs, fat FROM macros_targets WHERE id = 1")
    t = cur.fetchone()
    targets = dict(t) if t else {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
    # Sum consumed
    cur.execute("""SELECT
                      COALESCE(SUM(calories),0) as calories,
                      COALESCE(SUM(protein),0)  as protein,
                      COALESCE(SUM(carbs),0)    as carbs,
                      COALESCE(SUM(fat),0)      as fat
                   FROM consumption_log WHERE log_date = ?""", (qdate,))
    totals = dict(cur.fetchone())
    conn.close()
    remaining = {
        "calories": max(0.0, targets["calories"] - totals["calories"]),
        "protein":  max(0.0, targets["protein"]  - totals["protein"]),
        "carbs":    max(0.0, targets["carbs"]    - totals["carbs"]),
        "fat":      max(0.0, targets["fat"]      - totals["fat"]),
    }
    return jsonify({
        "date": qdate,
        "targets": targets,
        "consumed": totals,
        "remaining": remaining
    })

@app.route("/api/reset", methods=["POST"])
def reset_all():
    """Dangerous: wipe all data (keeps targets)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pantry")
    cur.execute("DELETE FROM consumption_log")
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
