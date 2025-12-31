from flask import Flask, request, jsonify
import psycopg2
import time
from datetime import datetime, timezone
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

DB_PARAMS = {
    "dbname": "seatdrops",
    "user": "postgres",
    "password": None,  # provided via CLI
    "host": "localhost",
    "port": 5432
}

def get_db():
    return psycopg2.connect(**DB_PARAMS)

@app.route("/query", methods=["POST"])
def query_course():
    data = request.json

    course_code = data["course_code"]      # e.g. "CSE 12"
    second_pass_open = datetime.fromisoformat(
        data["second_pass_open"].replace("Z", "+00:00")
    ).replace(tzinfo=timezone.utc)

    # Compute seconds since second pass
    now = datetime.now(timezone.utc)
    seconds_after = int((now - second_pass_open).total_seconds())

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT ON (s.section_id)
            s.section_label,
            s.quarter,
            s.capacity,
            COALESCE(e.time_after_second_pass_seconds, %s) AS time_after_second_pass_seconds,
            COALESCE(e.drops_after, 0) AS drops_after
        FROM sections s
        LEFT JOIN seat_drop_events e
            ON s.section_id = e.section_id AND e.time_after_second_pass_seconds >= %s
        WHERE
            s.course_code = %s
        ORDER BY
            s.section_id,
            e.time_after_second_pass_seconds ASC;
    """, (seconds_after, seconds_after, course_code))

    results = []
    for section, quarter, capacity, t, drops in cur.fetchall():
        results.append({
            "section": section,
            "quarter": quarter,
            "capacity": capacity,
            "seconds_after": t,
            "drops_after": drops,
        })

    cur.close()
    conn.close()

    return jsonify({
        "query_seconds_after": seconds_after,
        "sections": results
    })

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Flask app with DB credentials")
    parser.add_argument("--db-password", required=True, help="Postgres user's password")
    parser.add_argument("--host", default="127.0.0.1", help="Flask host")
    parser.add_argument("--port", type=int, default=5000, help="Flask port")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")

    args = parser.parse_args()

    DB_PARAMS["password"] = args.db_password

    app.run(debug=args.debug, host=args.host, port=args.port)