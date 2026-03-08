from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dsw_secret")

def db():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        port=os.environ.get("DB_PORT", 3306)
    )


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM employees WHERE email=%s", (email,))
        user = cursor.fetchone()

        # Check if user exists. We use check_password_hash, but fallback to plain text for your older test accounts!
        if user and (check_password_hash(user["password"], password) or user["password"] == password):
            session["user"] = user["email"]
            session["role"] = user["role"]
            if user["role"] == "manager":
                return redirect("/admin")
            else:
                return redirect("/dashboard")
        else:
            error = "Invalid email or password"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect("/")
    return render_template("dashboard.html")


@app.route("/attendance")
def attendance():
    if "user" not in session: return redirect("/")
    conn = db()
    cursor = conn.cursor()
    today = datetime.now().date()

    cursor.execute("SELECT * FROM attendance WHERE email=%s AND date=%s", (session["user"], today))
    if cursor.fetchone():
        return render_template("attendance.html", marked=True)

    now = datetime.now()
    cursor.execute("INSERT INTO attendance(email,date,time) VALUES(%s,%s,%s)",
                   (session["user"], now.date(), now.time()))
    conn.commit()
    return render_template("attendance.html", marked=False)


@app.route("/attendance_history")
def attendance_history():
    if "user" not in session: return redirect("/")
    conn = db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance WHERE email=%s ORDER BY date DESC", (session["user"],))
    return render_template("attendance_history.html", records=cursor.fetchall())


@app.route("/worklog", methods=["GET", "POST"])
def worklog():
    if "user" not in session: return redirect("/")
    if request.method == "POST":
        work = request.form["work"]
        now = datetime.now()  # Added time generation

        conn = db()
        cursor = conn.cursor()
        # Fixed bug: Now inserts date AND time into the worklog table
        cursor.execute("INSERT INTO worklog(email,work,date,time) VALUES(%s,%s,%s,%s)",
                       (session["user"], work, now.date(), now.time()))
        conn.commit()
        return redirect("/worklog_history")  # Redirect to history after submitting

    return render_template("worklog.html")


@app.route("/worklog_history")
def worklog_history():
    if "user" not in session: return redirect("/")
    conn = db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM worklog WHERE email=%s ORDER BY date DESC", (session["user"],))
    return render_template("worklog_history.html", logs=cursor.fetchall())


@app.route("/admin")
def admin():
    if session.get("role") != "manager": return redirect("/")
    conn = db()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM employees WHERE role='employee'")
    employees = cursor.fetchall()
    cursor.execute("SELECT * FROM attendance")
    attendance = cursor.fetchall()
    cursor.execute("SELECT * FROM worklog")
    worklogs = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS total FROM employees WHERE role='employee'")
    total_emp = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM attendance")
    total_att = cursor.fetchone()["total"]
    cursor.execute("SELECT COUNT(*) AS total FROM worklog")
    total_logs = cursor.fetchone()["total"]

    return render_template("admin_dashboard.html", employees=employees, attendance=attendance, worklogs=worklogs,
                           total_emp=total_emp, total_att=total_att, total_logs=total_logs)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("role") != "manager": return redirect("/")
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        # Enterprise Security: Hash the password before saving!
        hashed_pw = generate_password_hash(password)

        conn = db()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO employees(name,email,password,role) VALUES(%s,%s,%s,'employee')",
                       (name, email, hashed_pw))
        conn.commit()
        return redirect("/admin")
    return render_template("register.html")


@app.route("/attendance_calendar")
def attendance_calendar():
    if session.get("role") != "manager": return redirect("/")
    conn = db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM attendance")
    raw_records = cursor.fetchall()

    # FIXING THE CALENDAR BUG: Formatting time so FullCalendar doesn't crash
    formatted_records = []
    for r in raw_records:
        time_str = str(r['time'])
        if len(time_str) == 7:  # If MySQL returns "9:30:00", we make it "09:30:00"
            time_str = "0" + time_str

        formatted_records.append({
            "email": r["email"],
            "iso_start": f"{r['date']}T{time_str}"  # Creates perfect format: 2026-03-09T09:30:00
        })

    return render_template("attendance_calendar.html", records=formatted_records)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)