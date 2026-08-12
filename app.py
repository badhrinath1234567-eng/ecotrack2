from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import hashlib
import math
import os
from datetime import datetime

# ============================================================
# CONFIG
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "EcoTrack-development-secret-change-this"
)

DB = "smart_waste.db"


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()


def initialize_database():

    conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL,
            lat REAL DEFAULT 11.2588,
            lon REAL DEFAULT 75.7804
        );

        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citizen_id INTEGER NOT NULL,
            waste_type TEXT NOT NULL,
            photo_name TEXT,
            ai_classification TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            request_status TEXT DEFAULT 'Submitted',
            collector_id INTEGER,
            verification TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT NOT NULL
        );
    """)

    # Demo collector for testing.
    conn.execute(
        """
        INSERT OR IGNORE INTO users
        (
            name,
            email,
            password,
            user_type,
            lat,
            lon
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "Demo Collector",
            "collector@demo.com",
            hash_password("collector123"),
            "Collector",
            11.2650,
            75.7750
        )
    )

    conn.commit()
    conn.close()


initialize_database()


# ============================================================
# HELPERS
# ============================================================

def authenticate(email, password):

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE email = ?
        AND password = ?
        """,
        (
            email.strip().lower(),
            hash_password(password)
        )
    ).fetchone()

    conn.close()

    return user


def create_user(
    name,
    email,
    password,
    user_type,
    lat,
    lon
):

    conn = get_connection()

    try:

        conn.execute(
            """
            INSERT INTO users
            (
                name,
                email,
                password,
                user_type,
                lat,
                lon
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                email.strip().lower(),
                hash_password(password),
                user_type,
                lat,
                lon
            )
        )

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def distance_km(lat1, lon1, lat2, lon2):

    radius = 6371

    p1 = math.radians(lat1)
    p2 = math.radians(lat2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(p1)
        * math.cos(p2)
        * math.sin(dlon / 2) ** 2
    )

    return (
        2
        * radius
        * math.asin(math.sqrt(a))
    )


def nearest_collector(lat, lon):

    conn = get_connection()

    collectors = conn.execute(
        """
        SELECT *
        FROM users
        WHERE user_type = 'Collector'
        """
    ).fetchall()

    conn.close()

    if not collectors:
        return None, None

    collector = min(
        collectors,
        key=lambda c: distance_km(
            lat,
            lon,
            c["lat"],
            c["lon"]
        )
    )

    distance = distance_km(
        lat,
        lon,
        collector["lat"],
        collector["lon"]
    )

    return collector, distance


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ============================================================
# REGISTER
# ============================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "GET":

        return render_template(
            "register.html"
        )

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    user_type = request.form.get(
        "user_type",
        "Citizen"
    )

    lat_text = request.form.get(
        "lat",
        "11.2588"
    )

    lon_text = request.form.get(
        "lon",
        "75.7804"
    )

    # --------------------------------------------------------
    # VALIDATION
    # --------------------------------------------------------

    if not name or not email or not password:

        return render_template(
            "register.html",
            error="Please complete all fields."
        )

    if len(password) < 6:

        return render_template(
            "register.html",
            error="Password must contain at least 6 characters."
        )

    if user_type not in (
        "Citizen",
        "Collector"
    ):

        return render_template(
            "register.html",
            error="Invalid account type."
        )

    try:

        lat = float(lat_text)
        lon = float(lon_text)

    except ValueError:

        return render_template(
            "register.html",
            error="Latitude and longitude must be valid numbers."
        )

    if not -90 <= lat <= 90:

        return render_template(
            "register.html",
            error="Latitude must be between -90 and 90."
        )

    if not -180 <= lon <= 180:

        return render_template(
            "register.html",
            error="Longitude must be between -180 and 180."
        )

    # --------------------------------------------------------
    # CREATE ACCOUNT
    # --------------------------------------------------------

    created = create_user(
        name,
        email,
        password,
        user_type,
        lat,
        lon
    )

    if not created:

        return render_template(
            "register.html",
            error="An account with this email already exists."
        )

    return redirect(
        url_for("login")
    )


# ============================================================
# LOGIN
# ============================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "GET":

        return render_template(
            "login.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    if not email or not password:

        return render_template(
            "login.html",
            error="Enter your email and password."
        )

    user = authenticate(
        email,
        password
    )

    if not user:

        return render_template(
            "login.html",
            error="Invalid email or password."
        )

    session.clear()

    session["user_id"] = user["id"]
    session["user_type"] = user["user_type"]

    if user["user_type"] == "Citizen":

        return redirect(
            url_for("citizen")
        )

    if user["user_type"] == "Collector":

        return redirect(
            url_for("collector")
        )

    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(
        url_for("home")
    )


# ============================================================
# CITIZEN DASHBOARD
# ============================================================

@app.route("/citizen")
def citizen():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Citizen":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS collector_name
        FROM requests r
        LEFT JOIN users u
            ON r.collector_id = u.id
        WHERE r.citizen_id = ?
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    total = len(requests)

    completed = sum(
        1
        for r in requests
        if r["request_status"] == "Completed"
    )

    active = sum(
        1
        for r in requests
        if r["request_status"]
        not in ("Completed", "Closed")
    )

    return render_template(
        "citizen.html",
        user=user,
        requests=requests,
        total=total,
        active=active,
        completed=completed
    )


# ============================================================
# CITIZEN REQUEST
# ============================================================

@app.route(
    "/citizen/request",
    methods=["GET", "POST"]
)
def citizen_request():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Citizen":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    conn.close()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    if request.method == "GET":

        return render_template(
            "request.html",
            user=user
        )

    waste_type = request.form.get(
        "waste_type",
        ""
    ).strip()

    lat_text = request.form.get(
        "lat",
        ""
    )

    lon_text = request.form.get(
        "lon",
        ""
    )

    if not waste_type:

        return render_template(
            "request.html",
            user=user,
            error="Please select a waste type."
        )

    try:

        lat = float(lat_text)
        lon = float(lon_text)

    except ValueError:

        return render_template(
            "request.html",
            user=user,
            error="Please enter valid coordinates."
        )

    if not -90 <= lat <= 90:

        return render_template(
            "request.html",
            user=user,
            error="Invalid latitude."
        )

    if not -180 <= lon <= 180:

        return render_template(
            "request.html",
            user=user,
            error="Invalid longitude."
        )

    # --------------------------------------------------------
    # FIND NEAREST COLLECTOR
    # --------------------------------------------------------

    collector, distance = nearest_collector(
        lat,
        lon
    )

    collector_id = None

    if collector:

        collector_id = collector["id"]

    # --------------------------------------------------------
    # CREATE REQUEST
    # --------------------------------------------------------

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    conn = get_connection()

    conn.execute(
        """
        INSERT INTO requests
        (
            citizen_id,
            waste_type,
            ai_classification,
            lat,
            lon,
            request_status,
            collector_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session["user_id"],
            waste_type,
            waste_type,
            lat,
            lon,
            "Assigned" if collector else "Submitted",
            collector_id,
            created_at
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("citizen")
    )


# ============================================================
# CITIZEN REQUEST HISTORY
# ============================================================

@app.route("/citizen/requests")
def citizen_requests():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Citizen":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS collector_name
        FROM requests r
        LEFT JOIN users u
            ON r.collector_id = u.id
        WHERE r.citizen_id = ?
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "citizen.html",
        user=user,
        requests=requests,
        total=len(requests),
        active=sum(
            1
            for r in requests
            if r["request_status"]
            not in ("Completed", "Closed")
        ),
        completed=sum(
            1
            for r in requests
            if r["request_status"] == "Completed"
        )
    )


# ============================================================
# COLLECTOR DASHBOARD
# ============================================================

@app.route("/collector")
def collector():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS citizen_name
        FROM requests r
        JOIN users u
            ON r.citizen_id = u.id
        WHERE r.collector_id = ?
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    if not user:

        session.clear()

        return redirect(
            url_for("login")
        )

    total = len(requests)

    completed = sum(
        1
        for r in requests
        if r["request_status"] == "Completed"
    )

    active = sum(
        1
        for r in requests
        if r["request_status"]
        not in ("Completed", "Closed")
    )

    return render_template(
        "collector.html",
        user=user,
        requests=requests,
        total=total,
        active=active,
        completed=completed
    )


# ============================================================
# COLLECTOR REQUEST LIST
# ============================================================

@app.route("/collector/requests")
def collector_requests():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS citizen_name
        FROM requests r
        JOIN users u
            ON r.citizen_id = u.id
        WHERE r.collector_id = ?
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "collector_requests.html",
        user=user,
        requests=requests
    )


# ============================================================
# COLLECTOR COMPLETE REQUEST
# ============================================================

@app.route(
    "/collector/complete/<int:request_id>",
    methods=["POST"]
)
def complete_request(request_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    pickup = conn.execute(
        """
        SELECT *
        FROM requests
        WHERE id = ?
        AND collector_id = ?
        """,
        (
            request_id,
            session["user_id"]
        )
    ).fetchone()

    if not pickup:
        conn.close()
        return redirect(url_for("collector"))

    completed_at = datetime.now().isoformat(
        timespec="seconds"
    )

    conn.execute(
        """
        UPDATE requests
        SET
            request_status = 'Completed',
            verification = 'Verified',
            completed_at = ?
        WHERE id = ?
        AND collector_id = ?
        """,
        (
            completed_at,
            request_id,
            session["user_id"]
        )
    )

    conn.commit()
    conn.close()

    return redirect(
        url_for("collector")
    )


# ============================================================
# COLLECTOR NAVIGATION
# ============================================================

@app.route("/collector/navigation")
def collector_navigation():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS citizen_name
        FROM requests r
        JOIN users u
            ON r.citizen_id = u.id
        WHERE r.collector_id = ?
        AND r.request_status != 'Completed'
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "collector_navigation.html",
        user=user,
        requests=requests
    )


# ============================================================
# COLLECTOR VERIFY
# ============================================================

@app.route("/collector/verify")
def collector_verify():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    requests = conn.execute(
        """
        SELECT
            r.*,
            u.name AS citizen_name
        FROM requests r
        JOIN users u
            ON r.citizen_id = u.id
        WHERE r.collector_id = ?
        AND r.request_status != 'Completed'
        ORDER BY r.id DESC
        """,
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "collector_verify.html",
        user=user,
        requests=requests
    )


# ============================================================
# COLLECTOR ANALYTICS
# ============================================================

@app.route("/collector/analytics")
def collector_analytics():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Collector":
        return redirect(url_for("home"))

    conn = get_connection()

    user = conn.execute(
        """
        SELECT *
        FROM users
        WHERE id = ?
        """,
        (session["user_id"],)
    ).fetchone()

    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM requests
        WHERE collector_id = ?
        """,
        (session["user_id"],)
    ).fetchone()[0]

    completed = conn.execute(
        """
        SELECT COUNT(*)
        FROM requests
        WHERE collector_id = ?
        AND request_status = 'Completed'
        """,
        (session["user_id"],)
    ).fetchone()[0]

    active = total - completed

    conn.close()

    # The analytics page can use these values directly.
    return render_template(
        "collector_analytics.html",
        user=user,
        total=total,
        active=active,
        completed=completed
    )


# ============================================================
# FEEDBACK
# ============================================================

@app.route(
    "/citizen/feedback",
    methods=["GET", "POST"]
)
def feedback():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("user_type") != "Citizen":
        return redirect(url_for("home"))

    conn = get_connection()

    completed_requests = conn.execute(
        """
        SELECT id
        FROM requests
        WHERE citizen_id = ?
        AND request_status = 'Completed'
        ORDER BY id DESC
        """
        ,
        (session["user_id"],)
    ).fetchall()

    if request.method == "POST":

        try:

            request_id = int(
                request.form.get("request_id")
            )

            rating = int(
                request.form.get("rating")
            )

        except (
            ValueError,
            TypeError
        ):

            conn.close()

            return redirect(
                url_for("citizen")
            )

        comment = request.form.get(
            "comment",
            ""
        ).strip()

        if not 1 <= rating <= 5:

            conn.close()

            return redirect(
                url_for("citizen")
            )

        valid = conn.execute(
            """
            SELECT id
            FROM requests
            WHERE id = ?
            AND citizen_id = ?
            AND request_status = 'Completed'
            """,
            (
                request_id,
                session["user_id"]
            )
        ).fetchone()

        if not valid:

            conn.close()

            return redirect(
                url_for("citizen")
            )

        conn.execute(
            """
            INSERT INTO feedback
            (
                request_id,
                rating,
                comment,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                request_id,
                rating,
                comment,
                datetime.now().isoformat(
                    timespec="seconds"
                )
            )
        )

        conn.commit()
        conn.close()

        return redirect(
            url_for("citizen")
        )

    conn.close()

    return render_template(
        "feedback.html",
        requests=completed_requests
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return """
    <h1>404</h1>
    <p>Page not found.</p>
    <a href="/">Back to EcoTrack</a>
    """, 404


@app.errorhandler(500)
def server_error(error):
    return """
    <h1>Something went wrong.</h1>
    <p>Please return to EcoTrack and try again.</p>
    <a href="/">Back to EcoTrack</a>
    """, 500

# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )