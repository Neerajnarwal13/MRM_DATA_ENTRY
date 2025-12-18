import os
from io import BytesIO

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, send_file
)

# ---------------- APP CONFIG ----------------

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "railway-secret-key")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

# ---------------- DATABASE ----------------

def get_db():
    return psycopg2.connect(
        DATABASE_URL,
        sslmode="require",
        cursor_factory=RealDictCursor
    )

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # Main data table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plants (
            id SERIAL PRIMARY KEY,
            plant_name TEXT,
            month TEXT,
            run_time TEXT,
            fb TEXT,
            total_production NUMERIC,
            total_gas NUMERIC,
            total_sale NUMERIC,
            kwh NUMERIC,
            prod_breakdown TEXT,
            maint_breakdown TEXT,
            total_load NUMERIC,
            dg TEXT,
            diesel NUMERIC,
            electricity_bill NUMERIC,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Plant users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS plant_users (
            id SERIAL PRIMARY KEY,
            plant_name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Admin users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

@app.before_request
def before_request():
    if not hasattr(app, "db_ready"):
        init_db()
        app.db_ready = True

# ---------------- PLANT LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def plant_login():
    if request.method == "POST":
        plant_name = request.form.get("plant_name")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM plant_users WHERE plant_name=%s AND password=%s",
            (plant_name, password)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session.clear()
            session["plant_logged_in"] = True
            session["plant_name"] = plant_name
            return redirect(url_for("form"))
        else:
            flash("Invalid plant credentials", "danger")

    return render_template("plant_login.html")

@app.route("/plant-logout")
def plant_logout():
    session.clear()
    return redirect(url_for("plant_login"))

# ---------------- DATA ENTRY ----------------

@app.route("/form")
def form():
    if not session.get("plant_logged_in"):
        return redirect(url_for("plant_login"))
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    if not session.get("plant_logged_in"):
        return redirect(url_for("plant_login"))

    data = request.form

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO plants (
            plant_name, month, run_time, fb,
            total_production, total_gas, total_sale,
            kwh, prod_breakdown, maint_breakdown,
            total_load, dg, diesel, electricity_bill
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        session.get("plant_name"),
        data.get("month"),
        data.get("run_time"),
        data.get("fb"),
        data.get("total_production") or None,
        data.get("total_gas") or None,
        data.get("total_sale") or None,
        data.get("kwh") or None,
        data.get("prod_breakdown"),
        data.get("maint_breakdown"),
        data.get("total_load") or None,
        data.get("dg"),
        data.get("diesel") or None,
        data.get("electricity_bill") or None
    ))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("success.html")

# ---------------- ADMIN LOGIN ----------------

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM admins WHERE username=%s AND password=%s",
            (username, password)
        )
        admin = cur.fetchone()
        cur.close()
        conn.close()

        if admin:
            session.clear()
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        else:
            flash("Invalid admin credentials", "danger")

    return render_template("admin_login.html")

@app.route("/admin-logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))

# ---------------- ADMIN DASHBOARD ----------------

@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM plants ORDER BY created_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("admin.html", rows=rows)

# ---------------- EXPORT ----------------

@app.route("/export")
def export_excel():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
 id, plant_name, month, run_time, fb,
 total_production, total_gas, total_sale,
 kwh, prod_breakdown, maint_breakdown,
 total_load, dg, diesel, electricity_bill,
 created_at
FROM plants

        ORDER BY created_at DESC
    """)

    rows = cur.fetchall()
    columns = [desc[0] for desc in cur.description]

    cur.close()
    conn.close()

    # ✅ Create DataFrame PROPERLY
    df = pd.DataFrame(rows, columns=columns)

    output = BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="plant_data.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ---------------- RUN ----------------

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
