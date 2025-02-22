from flask import Flask, request, jsonify, render_template
import psycopg2
import os
import time
import requests

app = Flask(__name__, template_folder="frontend")

failed_attempts = {}

MAX_ATTEMPTS = 3
LOCKOUT_TIME = 60

HOME_ASSISTANT_URL = os.getenv("HA_WEBHOOK", "")

# Database connection
DB_HOST = os.getenv("DB_HOST", "postgres")
DB_USER = os.getenv("DB_USER", "myuser")
DB_PASSWORD = os.getenv("DB_PASSWORD", "password")
DB_NAME = os.getenv("DB_NAME", "passcodes")

API_SECRET = os.getenv("API_SECRET", "")

def create_table():
    conn = psycopg2.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD, dbname=DB_NAME
    )
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS passcodes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(10) NOT NULL,
            date DATE NOT NULL DEFAULT CURRENT_DATE
        );
    """)
    conn.commit()
    cur.close()
    conn.close()

# Call this function when Flask starts
create_table()

@app.route("/add_passcode", methods=["POST"])
def add_passcode():
    """Securely adds a single passcode, replacing the existing one."""
    print("Received a request!")
    print("Headers:", dict(request.headers))
    print("Body:", request.get_data(as_text=True))
    
    auth_header = request.headers.get("Authorization")

    if auth_header != f"Bearer {API_SECRET}":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    new_passcode = data.get("passcode")

    if not new_passcode:
        return jsonify({"message": "Passcode is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Ensure only one passcode exists: replace or insert
        cur.execute("DELETE FROM passcodes")  # Remove any existing passcode
        cur.execute("INSERT INTO passcodes (code, date) VALUES (%s, CURRENT_DATE)", (new_passcode,))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Passcode updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )

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

    # Check if user is in lockout period
    if attempts >= MAX_ATTEMPTS:
        if now - last_attempt < LOCKOUT_TIME:
            return jsonify({"message": "Too many failed attempts. Try again later."}), 429
        else:
            # Lockout period expired, reset attempts
            failed_attempts[client_ip] = {"count": 0, "last_attempt": 0}

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get the latest passcode
        cur.execute("SELECT code FROM passcodes ORDER BY date DESC LIMIT 1")
        result = cur.fetchone()

        cur.close()
        conn.close()

        if not result:
            return jsonify({"message": "No passcode found"}), 404

        correct_passcode = result[0]

        if correct_passcode == entered_passcode:
            # Reset failed attempts on success
            failed_attempts.pop(client_ip, None)
            try:
                response = requests.post(HOME_ASSISTANT_URL)
                if response.status_code == 200:
                    return jsonify({"message": "Access granted. Door opened."}), 200
                else:
                    return jsonify({"message": "Access granted, but failed to open door.", "error": response.text}), 500
            except requests.exceptions.RequestException as e:
                return jsonify({"message": "Access granted, but Home Assistant request failed.", "error": str(e)}), 500

        # Increment failed attempts on incorrect passcode
        failed_attempts[client_ip]["count"] += 1
        failed_attempts[client_ip]["last_attempt"] = now

        remaining_attempts = MAX_ATTEMPTS - failed_attempts[client_ip]["count"]

        return jsonify({"message": f"Access denied. {remaining_attempts} tries left."}), 403

    except Exception as e:
        return jsonify({"error": str(e)}), 500


    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
