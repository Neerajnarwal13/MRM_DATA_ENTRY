import os
from datetime import datetime
from io import BytesIO

import psycopg2
import pandas as pd
from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash, send_file
)

# ---------------- APP CONFIG ----------------

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "railway-secret-key")

# PostgreSQL (Railway auto provides this)
DATABASE_URL = os.getenv("DATABASE_URL")

# Admin credentials (Railway Variables)
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin123")

# Plant credentials (Railway Variables)
PLANT_USER = os.getenv("PLANT_USER", "plant1")
PLANT_PASS = os.getenv("PLANT_PASS", "plant123")

# ---------------- DATABASE ----------------

def get_db():
    return psycopg2.connect(DATABASE_URL)

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
            total_production DOUBLE PRECISION,
            total_gas DOUBLE PRECISION,
            total_sale DOUBLE PRECISION,
            kwh DOUBLE PRECISION,
            prod_breakdown TEXT,
            maint_breakdown TEXT,
            total_load DOUBLE PRECISION,
            dg TEXT,
            diesel DOUBLE PRECISION,
            electricity_bill DOUBLE PRECISION,
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
            request.form.get("plant_name") == PLANT_USER
            and request.form.get("password") == PLANT_PASS
        ):
            session["plant"] = True
            session["plant_name"] = request.form.get("plant_name")
            return redirect(url_for("form"))

        flash("Invalid plant name or password", "danger")

    return render_template("plant_login.html")

@app.route("/plant-logout")
def plant_logout():
    session.clear()
    return redirect(url_for("plant_login"))

# ---------------- DATA ENTRY FORM ----------------

@app.route("/form")
def form():
    if not session.get("plant"):
        return redirect(url_for("plant_login"))

    return render_template("form.html")

@app.route("/submit", methods=["POST"])
def submit():
    if not session.get("plant"):
        return redirect(url_for("plant_login"))

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO plants (
            plant_name, month, run_time, fb,
            total_production, total_gas, total_sale,
            kwh, prod_breakdown, maint_breakdown,
            total_load, dg, diesel, electricity_bill,
            created_at
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
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
        datetime.utcnow()
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

# ---------------- DELETE ----------------

@app.route("/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM plants WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()

    flash("Record deleted")
    return redirect(url_for("admin"))

# ---------------- EDIT ----------------

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit(id):
    if not session.get("admin"):
        return redirect(url_for("login"))

    conn = get_db()
    cur = conn.cursor()

    if request.method == "POST":
        cur.execute("""
            UPDATE plants SET
                plant_name=%s, month=%s, run_time=%s, fb=%s,
                total_production=%s, total_gas=%s, total_sale=%s,
                kwh=%s, prod_breakdown=%s, maint_breakdown=%s,
                total_load=%s, dg=%s, diesel=%s, electricity_bill=%s
            WHERE id=%s
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
        cur.close()
        conn.close()
        flash("Record updated")
        return redirect(url_for("admin"))

    cur.execute("SELECT * FROM plants WHERE id=%s", (id,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    return render_template("edit.html", row=row)

# ---------------- RUN ----------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
