import os
from datetime import datetime
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

# Admin login (Railway Variables)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# Plant login (Railway Variables)
PLANT_USER = os.getenv("PLANT_USER", "plant1")
PLANT_PASS = os.getenv("PLANT_PASS", "plant123")

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
            created_at TIMESTAMP
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

init_db()

# ---------------- PLANT LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def plant_login():
    if request.method == "POST":
        if (
            request.form.get("plant_name") == PLANT_USER and
            request.form.get("password") == PLANT_PASS
        ):
            session["plant"] = True
            return redirect(url_for("form"))

        flash("Invalid plant name or password", "danger")

    return render_template("plant_login.html")

@app.route("/plant-logout")
def plant_logout():
    session.pop("plant", None)
    return redirect(url_for("plant_login"))

# ---------------- DATA ENTRY ----------------

@app.route("/form")
def form():
    if not session.get("plant"):
        return redirect(url_for("plant_login"))
    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    if not session.get("plant"):
        return redirect(url_for("plant_login"))

    data = dict(request.form)
    created_at = datetime.utcnow()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO plants (
            plant_name, month, run_time, fb,
            total_production, total_gas, total_sale,
            kwh, prod_breakdown, maint_breakdown,
            total_load, dg, diesel, electricity_bill, created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        data["plant_name"],
        data["month"],
        data["run_time"],
        data["fb"],
        data["total_production"],
        data["total_gas"],
        data["total_sale"],
        data["kwh"],
        data["prod_breakdown"],
        data["maint_breakdown"],
        data["total_load"],
        data["dg"],
        data["diesel"],
        data["electricity_bill"],
        created_at
    ))

    conn.commit()
    cur.close()
    conn.close()

    return render_template("success.html")

# ---------------- ADMIN LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if (
            request.form.get("username") == ADMIN_USER and
            request.form.get("password") == ADMIN_PASS
        ):
            session["admin"] = True
            return redirect(url_for("admin"))

        flash("Invalid username or password", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- ADMIN PANEL ----------------

@app.route("/admin")
def admin():
    if not session.get("admin"):
        return redirect(url_for("login"))

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

# ---------------- RUN ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
