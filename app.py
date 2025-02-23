from flask import Flask, request, jsonify, render_template
import psycopg2
import os
import time
import requests

app = Flask(__name__, template_folder="frontend")

failed_attempts = {}

MAX_ATTEMPTS = 3
LOCKOUT_TIME = 60

# Database connection
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_USER = os.getenv("DB_USER", "myuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "passcodes")

API_SECRET = os.getenv("API_SECRET")
if not API_SECRET:
    raise ValueError("API_SECRET environment variable is missing!")

HOME_ASSISTANT_URL = os.getenv("HA_WEBHOOK")
if not HOME_ASSISTANT_URL:
    raise ValueError("HA_WEBHOOK environment variable is missing!")

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

def query_db(query, args=(), one=False):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, args)
            result = cur.fetchone() if one else cur.fetchall()
            conn.commit()
    return result

def create_table():
    for _ in range(10):  # Try for ~10 times
        try:
            query_db("""
                CREATE TABLE IF NOT EXISTS passcodes (
                    id SERIAL PRIMARY KEY,
                    code VARCHAR(10) NOT NULL,
                    date DATE NOT NULL DEFAULT CURRENT_DATE
                );
            """)
            print("Database initialized.")
            return
        except psycopg2.OperationalError as e:
            print(f"Database not ready: {e}")
            time.sleep(5)  # Wait before retrying

    print("Could not connect to database after multiple attempts. Exiting.")
    exit(1)

@app.route("/add_passcode", methods=["POST"])
def add_passcode():
    """Securely adds a single passcode, replacing the existing one."""
    auth_header = request.headers.get("Authorization")
    if auth_header != f"Bearer {API_SECRET}":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    new_passcode = data.get("passcode")
    if not new_passcode:
        return jsonify({"message": "Passcode is required"}), 400

    try:
        query_db("DELETE FROM passcodes")
        query_db("INSERT INTO passcodes (code, date) VALUES (%s, CURRENT_DATE)", (new_passcode,))
        return jsonify({"message": "Passcode updated successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check_passcode", methods=["POST"])
def check_passcode():
    """Checks if the entered passcode matches the latest one."""
    client_ip = request.remote_addr  # Get user's IP
    now = time.time()
    data = request.get_json()
    entered_passcode = data.get("passcode")

    if not entered_passcode:
        return jsonify({"error": "Passcode is required"}), 400

    if client_ip not in failed_attempts:
        failed_attempts[client_ip] = {"count": 0, "last_attempt": 0}

    attempts = failed_attempts[client_ip]["count"]
    last_attempt = failed_attempts[client_ip]["last_attempt"]

    if attempts >= MAX_ATTEMPTS and now - last_attempt < LOCKOUT_TIME:
        return jsonify({"message": "Too many failed attempts. Try again later."}), 429
    
    if attempts >= MAX_ATTEMPTS:
        failed_attempts[client_ip] = {"count": 0, "last_attempt": 0}

    try:
        result = query_db("SELECT code FROM passcodes ORDER BY date DESC LIMIT 1", one=True)
        if not result:
            return jsonify({"message": "No passcode found"}), 404

        correct_passcode = result[0]
        if correct_passcode == entered_passcode:
            failed_attempts.pop(client_ip, None)
            try:
                response = requests.post(HOME_ASSISTANT_URL)
                if response.status_code == 200:
                    return jsonify({"message": "Access granted. Door opened."}), 200
                else:
                    return jsonify({"message": "Access granted, but failed to open door.", "error": response.text}), 500
            except requests.exceptions.RequestException as e:
                return jsonify({"message": "Access granted, but Home Assistant request failed.", "error": str(e)}), 500

        failed_attempts[client_ip]["count"] += 1
        failed_attempts[client_ip]["last_attempt"] = now
        remaining_attempts = MAX_ATTEMPTS - failed_attempts[client_ip]["count"]
        return jsonify({"message": f"Access denied. {remaining_attempts} tries left."}), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    create_table()
    app.run(host="0.0.0.0", port=5000, debug=True)
