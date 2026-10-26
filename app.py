from datetime import datetime
from pathlib import Path
import os
import re
import sqlite3

from flask import Flask, jsonify, render_template, request

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("FOOD_DONATION_DB", BASE_DIR / "instance" / "food_donation.db"))

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            food_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity REAL NOT NULL CHECK(quantity > 0),
            unit TEXT NOT NULL,
            expiry_datetime TEXT NOT NULL,
            pickup_location TEXT NOT NULL,
            donor_name TEXT NOT NULL,
            donor_contact TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Available'
                CHECK(status IN ('Available', 'Reserved', 'Completed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS donation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL REFERENCES donations(id),
            recipient_name TEXT NOT NULL,
            recipient_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending'
                CHECK(status IN ('Pending', 'Approved', 'Rejected', 'Completed')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def row_to_dict(row):
    return dict(row) if row else None


def validate_donation(data):
    required = [
        "food_name", "category", "unit", "expiry_datetime",
        "pickup_location", "donor_name", "donor_contact"
    ]
    missing = [field for field in required if not str(data.get(field, "")).strip()]
    if missing:
        return f"Required fields missing: {', '.join(missing)}"

    try:
        quantity = float(data.get("quantity", 0))
    except (TypeError, ValueError):
        return "Quantity must be a valid number."
    if quantity <= 0:
        return "Quantity must be greater than zero."

    try:
        expiry = datetime.fromisoformat(str(data["expiry_datetime"]).replace("Z", "+00:00"))
        if expiry.tzinfo:
            expiry = expiry.replace(tzinfo=None)
    except ValueError:
        return "Expiry date and time must be valid."

    if expiry <= datetime.now():
        return "Expiry date and time must be in the future."

    contact = str(data["donor_contact"]).strip()
    if len(contact) < 5:
        return "Donor contact must contain at least 5 characters."
    return None


def validate_request(data):
    name = str(data.get("recipient_name", "")).strip()
    contact = str(data.get("recipient_contact", "")).strip()
    if not name or not contact:
        return "Recipient name and contact are required."
    if len(contact) < 5:
        return "Recipient contact must contain at least 5 characters."
    return None


def donation_is_expired(value):
    try:
        expiry = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if expiry.tzinfo:
            expiry = expiry.replace(tzinfo=None)
        return expiry <= datetime.now()
    except ValueError:
        return True


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/donations")
def list_donations():
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    sql = "SELECT * FROM donations WHERE 1=1"
    params = []
    if search:
        sql += " AND (food_name LIKE ? OR pickup_location LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term])
    if category:
        sql += " AND category = ?"
        params.append(category)
    if status:
        sql += " AND status = ?"
        params.append(status)
        if status == "Available":
            sql += " AND datetime(expiry_datetime) > datetime('now', 'localtime')"
    sql += " ORDER BY id DESC"
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.get("/api/donations/<int:donation_id>")
def get_donation(donation_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
    if not row:
        return jsonify(error="Donation not found."), 404
    return jsonify(row_to_dict(row))


@app.post("/api/donations")
def create_donation():
    data = request.get_json(silent=True) or {}
    error = validate_donation(data)
    if error:
        return jsonify(error=error), 400

    fields = (
        str(data["food_name"]).strip(), str(data["category"]).strip(),
        float(data["quantity"]), str(data["unit"]).strip(),
        str(data["expiry_datetime"]).strip(), str(data["pickup_location"]).strip(),
        str(data["donor_name"]).strip(), str(data["donor_contact"]).strip(),
        str(data.get("notes", "")).strip()
    )
    with get_db() as conn:
        cur = conn.execute("""
            INSERT INTO donations
            (food_name, category, quantity, unit, expiry_datetime, pickup_location,
             donor_name, donor_contact, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, fields)
        row = conn.execute("SELECT * FROM donations WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(donation=row_to_dict(row), message="Donation created successfully."), 201


@app.put("/api/donations/<int:donation_id>")
def update_donation(donation_id):
    data = request.get_json(silent=True) or {}
    error = validate_donation(data)
    if error:
        return jsonify(error=error), 400

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
        if not row:
            conn.rollback()
            return jsonify(error="Donation not found."), 404
        if row["status"] != "Available":
            conn.rollback()
            return jsonify(error="Only Available donations can be edited."), 409

        conn.execute("""
            UPDATE donations SET food_name=?, category=?, quantity=?, unit=?,
            expiry_datetime=?, pickup_location=?, donor_name=?, donor_contact=?,
            notes=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (
            str(data["food_name"]).strip(), str(data["category"]).strip(),
            float(data["quantity"]), str(data["unit"]).strip(),
            str(data["expiry_datetime"]).strip(), str(data["pickup_location"]).strip(),
            str(data["donor_name"]).strip(), str(data["donor_contact"]).strip(),
            str(data.get("notes", "")).strip(), donation_id
        ))
        updated = conn.execute("SELECT * FROM donations WHERE id = ?", (donation_id,)).fetchone()
        conn.commit()
    return jsonify(donation=row_to_dict(updated), message="Donation updated successfully.")


@app.get("/api/requests")
def list_requests():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT r.*, d.food_name, d.pickup_location, d.status AS donation_status
            FROM donation_requests r JOIN donations d ON d.id = r.donation_id
            ORDER BY r.id DESC
        """).fetchall()
    return jsonify([row_to_dict(row) for row in rows])


@app.post("/api/donations/<int:donation_id>/requests")
def create_request(donation_id):
    data = request.get_json(silent=True) or {}
    error = validate_request(data)
    if error:
        return jsonify(error=error), 400

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        donation = conn.execute("SELECT * FROM donations WHERE id=?", (donation_id,)).fetchone()
        if not donation:
            conn.rollback()
            return jsonify(error="Donation not found."), 404
        if donation["status"] != "Available":
            conn.rollback()
            return jsonify(error="This donation is not available for requests."), 409
        if donation_is_expired(donation["expiry_datetime"]):
            conn.rollback()
            return jsonify(error="Expired donations cannot be requested."), 409

        cur = conn.execute("""
            INSERT INTO donation_requests (donation_id, recipient_name, recipient_contact)
            VALUES (?, ?, ?)
        """, (donation_id, str(data["recipient_name"]).strip(), str(data["recipient_contact"]).strip()))
        conn.execute("""
            UPDATE donations SET status='Reserved', updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (donation_id,))
        row = conn.execute("""
            SELECT r.*, d.food_name, d.status AS donation_status
            FROM donation_requests r JOIN donations d ON d.id=r.donation_id
            WHERE r.id=?
        """, (cur.lastrowid,)).fetchone()
        conn.commit()
    return jsonify(request=row_to_dict(row), message="Request submitted successfully."), 201


@app.patch("/api/requests/<int:request_id>/decision")
def update_request_status(request_id):
    data = request.get_json(silent=True) or {}
    action = str(data.get("action", "")).strip().lower()
    if action not in {"approve", "reject", "complete"}:
        return jsonify(error="Action must be approve, reject or complete."), 400

    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("""
            SELECT r.*, d.status AS donation_status, d.expiry_datetime
            FROM donation_requests r JOIN donations d ON d.id=r.donation_id
            WHERE r.id=?
        """, (request_id,)).fetchone()
        if not row:
            conn.rollback()
            return jsonify(error="Request not found."), 404

        current = row["status"]
        donation_id = row["donation_id"]

        if action == "approve":
            if current != "Pending":
                conn.rollback()
                return jsonify(error="Only Pending requests can be approved."), 409
            new_status = "Approved"
            conn.execute("""
                UPDATE donation_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (new_status, request_id))

        elif action == "reject":
            if current != "Pending":
                conn.rollback()
                return jsonify(error="Only Pending requests can be rejected."), 409
            new_status = "Rejected"
            conn.execute("""
                UPDATE donation_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (new_status, request_id))
            if not donation_is_expired(row["expiry_datetime"]):
                conn.execute("""
                    UPDATE donations SET status='Available', updated_at=CURRENT_TIMESTAMP WHERE id=?
                """, (donation_id,))

        else:
            if current != "Approved":
                conn.rollback()
                return jsonify(error="Only Approved requests can be completed."), 409
            new_status = "Completed"
            conn.execute("""
                UPDATE donation_requests SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (new_status, request_id))
            conn.execute("""
                UPDATE donations SET status='Completed', updated_at=CURRENT_TIMESTAMP WHERE id=?
            """, (donation_id,))

        updated = conn.execute("""
            SELECT r.*, d.food_name, d.status AS donation_status
            FROM donation_requests r JOIN donations d ON d.id=r.donation_id
            WHERE r.id=?
        """, (request_id,)).fetchone()
        conn.commit()
    return jsonify(request=row_to_dict(updated), message=f"Request {new_status.lower()}.")


@app.get("/api/categories")
def list_categories():
    with get_db() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM donations ORDER BY category").fetchall()
    return jsonify([row["category"] for row in rows])


@app.errorhandler(500)
def server_error(_error):
    return jsonify(error="An unexpected server error occurred. Check the server terminal."), 500


init_db()

if __name__ == "__main__":
    app.run(debug=True)
