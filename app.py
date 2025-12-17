import os
import sqlite3
from datetime import datetime
from io import BytesIO

import pandas as pd
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, send_file
)

# ---------------- APP CONFIG ----------------

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "railway-secret-key")

DATABASE = "plant_data.db"
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # ⚠️ IMPORTANT: reset old broken table
    conn.execute("DROP TABLE IF EXISTS plants")

    conn.execute("""
        CREATE TABLE plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_name TEXT,
            month TEXT,
            run_time TEXT,
            fb TEXT,
            total_production REAL,
            total_gas REAL,
            total_sale REAL,
            kwh REAL,
            prod_breakdown TEXT,
            maint_breakdown TEXT,
            total_load REAL,
            dg TEXT,
            diesel REAL,
            electricity_bill REAL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- PUBLIC ----------------

@app.route("/")
def index():
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    data = dict(request.form)
    data["created_at"] = datetime.utcnow().isoformat()

    conn = get_db()
    conn.execute("""
        INSERT INTO plants VALUES (
            NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    """, tuple(data.values()))
    conn.commit()
    conn.close()

    return render_template("success.html")

# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USER
            and request.form.get("password") == ADMIN_PASS
        ):
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Invalid username or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- ADMIN ----------------

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM plants ORDER BY created_at DESC"
    ).fetchall()
    conn.close()

    return render_template("admin.html", rows=rows)

# ---------------- EXPORT ----------------

@app.route("/export")
def export_excel():
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    df = pd.read_sql("SELECT * FROM plants", conn)
    conn.close()

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="plant_data.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- DELETE ----------------

@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    conn.execute("DELETE FROM plants WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    flash("Record deleted")
    return redirect(url_for("admin"))

# ---------------- EDIT ----------------

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()

    if request.method == "POST":
        conn.execute("""
            UPDATE plants SET
                plant_name = ?,
                month = ?,
                run_time = ?,
                fb = ?,
                total_production = ?,
                total_gas = ?,
                total_sale = ?,
                kwh = ?,
                prod_breakdown = ?,
                maint_breakdown = ?,
                total_load = ?,
                dg = ?,
                diesel = ?,
                electricity_bill = ?
            WHERE id = ?
        """, (
            request.form["plant_name"],
            request.form["month"],
            request.form["run_time"],
            request.form["fb"],
            request.form["total_production"],
            request.form["total_gas"],
            request.form["total_sale"],
            request.form["kwh"],
            request.form["prod_breakdown"],
            request.form["maint_breakdown"],
            request.form["total_load"],
            request.form["dg"],
            request.form["diesel"],
            request.form["electricity_bill"],
            id
        ))

        conn.commit()
        conn.close()
        flash("Record updated")
        return redirect(url_for("admin"))

    row = conn.execute(
        "SELECT * FROM plants WHERE id = ?", (id,)
    ).fetchone()
    conn.close()

    return render_template("edit.html", row=row)

# ---------------- RUN ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
