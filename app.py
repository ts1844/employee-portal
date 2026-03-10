from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dsw_secret")


def db():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "MySQL"),
        database=os.environ.get("DB_NAME", "employee_portal"),
        port=int(os.environ.get("DB_PORT", 3306))
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

    conn = db()
    cursor = conn.cursor(dictionary=True)
    today = datetime.now().date()

    # 1. Check if the employee is already clocked in today
    cursor.execute("SELECT * FROM attendance WHERE email=%s AND date=%s", (session["user"], today))
    clocked_in = cursor.fetchone() is not None

    # 2. Get their 3 most recent work logs for the activity feed
    cursor.execute("SELECT * FROM worklog WHERE email=%s ORDER BY date DESC, time DESC LIMIT 3", (session["user"],))
    recent_logs = cursor.fetchall()

    # Calculate the duration for each recent log to show on the dashboard
    for log in recent_logs:
        if log.get('start_time') and log.get('end_time'):
            diff = log['end_time'] - log['start_time']
            total_seconds = int(diff.total_seconds())

            if total_seconds < 0:
                total_seconds += 24 * 3600

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            if hours > 0:
                log['duration_str'] = f"{hours}h {minutes}m"
            else:
                log['duration_str'] = f"{minutes}m"
        else:
            log['duration_str'] = None

    return render_template("dashboard.html", clocked_in=clocked_in, recent_logs=recent_logs)


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
    cursor.execute("SELECT * FROM attendance WHERE email=%s", (session["user"],))
    raw_records = cursor.fetchall()

    # Format the time securely for the JavaScript Calendar
    formatted_records = []
    for r in raw_records:
        time_str = str(r['time'])
        if len(time_str) == 7:
            time_str = "0" + time_str

        formatted_records.append({
            "iso_start": f"{r['date']}T{time_str}"
        })

    return render_template("attendance_history.html", records=formatted_records)


@app.route("/worklog", methods=["GET", "POST"])
def worklog():
    if "user" not in session: return redirect("/")

    if request.method == "POST":
        work = request.form["work"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        now = datetime.now()

        conn = db()
        cursor = conn.cursor()

        # Insert the new start_time and end_time into the database
        cursor.execute(
            "INSERT INTO worklog(email,work,date,time,start_time,end_time) VALUES(%s,%s,%s,%s,%s,%s)",
            (session["user"], work, now.date(), now.time(), start_time, end_time)
        )
        conn.commit()

        flash("Work log and task duration submitted successfully!", "success")
        return redirect("/worklog_history")

    return render_template("worklog.html")


@app.route("/worklog_history")
def worklog_history():
    if "user" not in session: return redirect("/")

    conn = db()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM worklog WHERE email=%s ORDER BY date DESC, time DESC", (session["user"],))
    logs = cursor.fetchall()

    # Calculate the duration for each log
    for log in logs:
        if log.get('start_time') and log.get('end_time'):
            # MySQL 'TIME' columns come back as timedelta objects
            diff = log['end_time'] - log['start_time']
            total_seconds = int(diff.total_seconds())

            # Handle edge case: if a task crosses midnight (e.g., 11 PM to 1 AM)
            if total_seconds < 0:
                total_seconds += 24 * 3600

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            # Format nicely as "2h 15m" or just "45m"
            if hours > 0:
                log['duration_str'] = f"{hours}h {minutes}m"
            else:
                log['duration_str'] = f"{minutes}m"
        else:
            log['duration_str'] = None

    return render_template("worklog_history.html", logs=logs)


@app.route("/admin")
def admin():
    if session.get("role") != "manager": return redirect("/")

    conn = db()
    cursor = conn.cursor(dictionary=True)
    today = datetime.now().date()

    # 1. Fetch raw table data
    cursor.execute("SELECT * FROM employees WHERE role='employee'")
    employees = cursor.fetchall()

    cursor.execute("SELECT * FROM attendance ORDER BY date DESC, time DESC")
    attendance = cursor.fetchall()

    cursor.execute("SELECT * FROM worklog ORDER BY date DESC, time DESC")
    worklogs = cursor.fetchall()

    # NEW: Calculate the duration for all global work logs
    for log in worklogs:
        if log.get('start_time') and log.get('end_time'):
            diff = log['end_time'] - log['start_time']
            total_seconds = int(diff.total_seconds())

            if total_seconds < 0:
                total_seconds += 24 * 3600

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            if hours > 0:
                log['duration_str'] = f"{hours}h {minutes}m"
            else:
                log['duration_str'] = f"{minutes}m"
        else:
            log['duration_str'] = None

    # 2. Calculate Today's Real-Time KPIs
    cursor.execute("SELECT COUNT(*) AS total FROM employees WHERE role='employee'")
    total_emp = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM attendance WHERE date=%s", (today,))
    today_att = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM worklog WHERE date=%s", (today,))
    today_logs = cursor.fetchone()["total"]

    # 3. Build a Live Activity Feed for Today
    cursor.execute("""
        SELECT 'Clock-In' as type, email, time FROM attendance WHERE date=%s
        UNION ALL
        SELECT 'Work Log' as type, email, time FROM worklog WHERE date=%s
        ORDER BY time DESC LIMIT 6
    """, (today, today))
    activity = cursor.fetchall()

    return render_template(
        "admin_dashboard.html",
        employees=employees, attendance=attendance, worklogs=worklogs,
        total_emp=total_emp, today_att=today_att, today_logs=today_logs,
        activity=activity
    )

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