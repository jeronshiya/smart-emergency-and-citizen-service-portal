import math
import os
import smtplib
from datetime import date, datetime, time
from email.message import EmailMessage

from flask import Flask, jsonify, render_template, request, redirect, session
from database import get_connection


app = Flask(__name__)

app.secret_key = "smart_emergency_secret"


def ensure_saved_facilities_table(cursor):
    if app.extensions.get("saved_facilities_table_ready"):
        return

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_facilities (
            saved_facility_id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            service_type VARCHAR(20) NOT NULL,
            osm_type VARCHAR(10) NOT NULL,
            osm_id BIGINT NOT NULL,
            name VARCHAR(255) NOT NULL,
            address VARCHAR(1000) NOT NULL,
            latitude DECIMAL(10, 7) NOT NULL,
            longitude DECIMAL(10, 7) NOT NULL,
            distance_km DECIMAL(8, 2) NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_saved_facility (user_id, service_type, osm_type, osm_id),
            CONSTRAINT fk_saved_facilities_user
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )
    app.extensions["saved_facilities_table_ready"] = True


def close_database(cursor, conn):
    if cursor:
        cursor.close()
    if conn:
        conn.close()


def send_complaint_notification(complaint_id, category, location, description, user_name):

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    admin_email = os.getenv("ADMIN_EMAIL", smtp_user)

    if not smtp_user or not smtp_password or not admin_email:
        app.logger.warning("Complaint email skipped: SMTP settings are not configured")
        return False

    message = EmailMessage()
    message["Subject"] = f"New Citizen Complaint #{complaint_id}"
    message["From"] = smtp_user
    message["To"] = admin_email
    message.set_content(
        f"A new complaint was submitted.\n\n"
        f"Complaint ID: {complaint_id}\n"
        f"Citizen: {user_name}\n"
        f"Category: {category}\n"
        f"Location: {location}\n"
        f"Description: {description}\n"
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(smtp_user, smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as error:
        app.logger.exception("Complaint email notification failed: %s", error)
        return False


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/nearby-hospitals")
def nearby_hospitals():
    return render_template(
        "nearby_service.html",
        title="Nearby Hospitals",
        facility_name="Hospital",
        search_term="hospitals",
        overpass_filters=(
            'nwr[amenity~"^(hospital|clinic|doctors)$"];'
            'nwr[healthcare~"^(hospital|clinic|doctor|centre|health_centre|urgent_care)$"];'
        ),
        is_authenticated="user_id" in session,
    )


@app.route("/nearby-blood-banks")
def nearby_blood_banks():
    return render_template(
        "nearby_service.html",
        title="Nearby Blood Banks",
        facility_name="Blood Bank",
        search_term="blood banks",
        overpass_filters="nwr[amenity=blood_bank];nwr[amenity=blood_donation];nwr[healthcare=blood_bank];",
        is_authenticated="user_id" in session,
    )


@app.route("/saved-places")
def saved_places():
    if "user_id" not in session:
        return redirect("/login?next=/saved-places")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        ensure_saved_facilities_table(cursor)
        cursor.execute(
            """
            SELECT saved_facility_id, service_type, name, address, latitude,
                   longitude, distance_km, saved_at
            FROM saved_facilities
            WHERE user_id=%s
            ORDER BY saved_at DESC, saved_facility_id DESC
            """,
            (session["user_id"],)
        )
        places = cursor.fetchall()
    finally:
        close_database(cursor, conn)

    return render_template("saved_places.html", places=places)


@app.route("/api/saved-facilities", methods=["POST"])
def save_facility():
    if "user_id" not in session:
        return jsonify(error="Please log in to save a place.", login_url="/login"), 401

    facility = request.get_json(silent=True)
    if not isinstance(facility, dict):
        return jsonify(error="Invalid facility details."), 400

    service_type = facility.get("service_type")
    osm_type = facility.get("osm_type")
    osm_id = facility.get("osm_id")
    name = facility.get("name")
    address = facility.get("address")
    latitude = facility.get("latitude")
    longitude = facility.get("longitude")
    distance_km = facility.get("distance_km")

    if service_type not in ("hospital", "blood_bank"):
        return jsonify(error="Invalid facility type."), 400
    if osm_type not in ("node", "way", "relation"):
        return jsonify(error="Invalid facility identifier."), 400
    if isinstance(osm_id, bool) or not isinstance(osm_id, int) or not 0 < osm_id < 2**63:
        return jsonify(error="Invalid facility identifier."), 400
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 255:
        return jsonify(error="A valid facility name is required."), 400
    if not isinstance(address, str) or len(address) > 1000:
        return jsonify(error="Invalid facility address."), 400

    numbers = (latitude, longitude, distance_km)
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in numbers):
        return jsonify(error="Invalid facility location or distance."), 400
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or distance_km < 0:
        return jsonify(error="Invalid facility location or distance."), 400

    conn = get_connection()
    cursor = conn.cursor()
    try:
        ensure_saved_facilities_table(cursor)
        cursor.execute(
            """
            INSERT INTO saved_facilities
                (user_id, service_type, osm_type, osm_id, name, address,
                 latitude, longitude, distance_km)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name),
                address=VALUES(address),
                latitude=VALUES(latitude),
                longitude=VALUES(longitude),
                distance_km=VALUES(distance_km)
            """,
            (
                session["user_id"], service_type, osm_type, osm_id, name.strip(),
                address, latitude, longitude, distance_km
            )
        )
        conn.commit()
        return jsonify(message="Place saved to your account.")
    except Exception:
        conn.rollback()
        app.logger.exception("Unable to save nearby facility")
        return jsonify(error="The place could not be saved. Please try again."), 500
    finally:
        close_database(cursor, conn)


@app.route("/saved-places/<int:saved_facility_id>/delete", methods=["POST"])
def delete_saved_place(saved_facility_id):
    if "user_id" not in session:
        return redirect("/login?next=/saved-places")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        ensure_saved_facilities_table(cursor)
        cursor.execute(
            "DELETE FROM saved_facilities WHERE saved_facility_id=%s AND user_id=%s",
            (saved_facility_id, session["user_id"])
        )
        conn.commit()
    except Exception:
        conn.rollback()
        app.logger.exception("Unable to remove saved facility")
        return "The saved place could not be removed. Please try again.", 500
    finally:
        close_database(cursor, conn)

    return redirect("/saved-places")


# =========================================================
# USER REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        password = request.form.get("password")
        address = request.form.get("address", "")
        city = request.form.get("city", "")
        pincode = request.form.get("pincode", "")

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users
                (full_name, email, mobile, password, address, city, pincode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    full_name,
                    email,
                    mobile,
                    password,
                    address,
                    city,
                    pincode
                )
            )
            conn.commit()
            cursor.close()
            conn.close()

            return redirect("/login")

        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            return "Registration Error: " + str(e)

    return render_template("register.html")


# =========================================================
# USER LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        next_url = request.form.get("next", "")
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email=%s
            AND password=%s
            """,
            (email, password)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user:
            session["user_id"] = user["user_id"]
            session["user_name"] = user["full_name"]
            if next_url in ("/nearby-hospitals", "/nearby-blood-banks", "/saved-places"):
                return redirect(next_url)
            return redirect("/dashboard")

        return "Invalid Email or Password"

    return render_template("login.html", next_url=request.args.get("next", ""))


# =========================================================
# USER DASHBOARD & SOS
# =========================================================

@app.route("/sos", methods=["GET", "POST"])
def sos():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        emergency_date_value = request.form.get("emergency_datetime", "")
        try:
            emergency_date = date.fromisoformat(emergency_date_value)
            if emergency_date.isoformat() != emergency_date_value:
                raise ValueError("Invalid date format")
        except ValueError:
            return render_template(
                "sos.html",
                today_date=date.today().isoformat(),
                selected_emergency_date=emergency_date_value,
                error_message="Please enter a valid emergency date.",
                ambulance_request=request.form.get("service_mode") == "ambulance",
            ), 400

        if emergency_date < date.today():
            return render_template(
                "sos.html",
                today_date=date.today().isoformat(),
                selected_emergency_date=emergency_date_value,
                error_message="Emergency date cannot be earlier than today.",
                ambulance_request=request.form.get("service_mode") == "ambulance",
            ), 400

        conn = get_connection()
        cursor = conn.cursor()

        # Added fallback value to avoid column cannot be null error
        emergency_type = request.form.get("emergency_type") or "General Emergency"
        location = request.form.get("location")
        description = request.form.get("description")

        cursor.execute(
            """
            INSERT INTO sos_requests
            (user_id, emergency_type, location, description, emergency_datetime, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                emergency_type,
                location,
                description,
                datetime.combine(emergency_date, time.min),
                "Pending"
            )
        )
        conn.commit()
        cursor.close()
        conn.close()

        return redirect("/dashboard")

    return render_template("sos.html", today_date=date.today().isoformat())


@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        conn = get_connection()
        cursor = conn.cursor()

        category = request.form.get("category")
        location = request.form.get("location")
        description = request.form.get("description")

        cursor.execute(
            """
            INSERT INTO complaints
            (user_id, category, location, description, status)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                session["user_id"],
                category,
                location,
                description,
                "Pending"
            )
        )
        complaint_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()

        send_complaint_notification(
            complaint_id,
            category,
            location,
            description,
            session.get("user_name", "Citizen")
        )

        return redirect("/dashboard")

    return render_template("citizen_complaint.html")


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    return render_template(
        "dashboard.html",
        user_name=session.get("user_name"),
        name=session.get("user_name")
    )


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT full_name, email, mobile, address, city, pincode FROM users WHERE user_id=%s",
        (session["user_id"],)
    )
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    return render_template("profile.html", user=user)


@app.route("/status")
def status():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT sos_id, emergency_type, location, description, emergency_datetime, status, created_at
        FROM sos_requests
        WHERE user_id=%s
        ORDER BY sos_id DESC
        """,
        (session["user_id"],)
    )
    sos_requests = cursor.fetchall()

    cursor.execute(
        """
        SELECT complaint_id, category, location, description, status, created_at
        FROM complaints
        WHERE user_id=%s
        ORDER BY complaint_id DESC
        """,
        (session["user_id"],)
    )
    complaints = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "status.html",
        sos_requests=sos_requests,
        complaints=complaints
    )


# =========================================================
# USER LOGOUT
# =========================================================

@app.route("/user-logout")
def user_logout():
    session.clear()
    return redirect("/")


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM admins
            WHERE username=%s
            AND password=%s
            """,
            (username, password)
        )

        admin = cursor.fetchone()

        cursor.close()
        conn.close()

        if admin:
            session["admin_id"] = admin["admin_id"]
            return redirect("/admin-dashboard")

        return "Invalid Admin Login"

    return render_template("admin_login.html")


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin-dashboard")
def admin_dashboard():
    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM sos_requests")
    total_sos = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_complaints = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return render_template(
        "admin_dashboard.html",
        total_users=total_users,
        total_sos=total_sos,
        total_complaints=total_complaints
    )


# =========================================================
# ADMIN - VIEW USERS
# =========================================================

@app.route("/admin-users")
def admin_users():
    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            user_id,
            full_name,
            email,
            mobile,
            address,
            city,
            pincode
        FROM users
        ORDER BY user_id DESC
        """
    )
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_users.html", users=users)


# =========================================================
# ADMIN - VIEW & UPDATE SOS
# =========================================================

@app.route("/admin-sos")
def admin_sos():
    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            sos_requests.sos_id,
            sos_requests.emergency_type,
            sos_requests.location,
            sos_requests.description,
            sos_requests.emergency_datetime,
            sos_requests.status,
            users.full_name,
            users.mobile
        FROM sos_requests
        INNER JOIN users
        ON sos_requests.user_id = users.user_id
        ORDER BY sos_requests.sos_id DESC
        """
    )
    sos_list = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_sos.html", sos_list=sos_list)


@app.route("/update-sos/<int:sos_id>", methods=["POST"])
def update_sos(sos_id):
    if "admin_id" not in session:
        return redirect("/admin-login")

    status = request.form.get("status")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE sos_requests
        SET status=%s
        WHERE sos_id=%s
        """,
        (status, sos_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/admin-sos")


# =========================================================
# ADMIN - VIEW & UPDATE COMPLAINTS
# =========================================================

@app.route("/admin-complaints")
def admin_complaints():
    if "admin_id" not in session:
        return redirect("/admin-login")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            complaints.complaint_id,
            complaints.category,
            complaints.location,
            complaints.description,
            complaints.status,
            users.full_name,
            users.mobile
        FROM complaints
        INNER JOIN users
        ON complaints.user_id = users.user_id
        ORDER BY complaints.complaint_id DESC
        """
    )
    complaints = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("complaint.html", complaints=complaints)


@app.route("/update-complaint/<int:complaint_id>", methods=["POST"])
def update_complaint(complaint_id):
    if "admin_id" not in session:
        return redirect("/admin-login")

    status = request.form.get("status")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE complaints
        SET status=%s
        WHERE complaint_id=%s
        """,
        (status, complaint_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect("/admin-complaints")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":
    app.run(debug=True)