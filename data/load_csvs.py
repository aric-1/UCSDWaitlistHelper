import os
import re
import pandas as pd
import psycopg2
import argparse

# ---------- CONFIG ----------
CSV_ROOT = "./csvs"
DB_PARAMS = {
    "dbname": "seatdrops",
    "user": "postgres",
    "password": None,  # provided via CLI
    "host": "localhost",
    "port": 5432
}
# ----------------------------

# Regex to parse filenames like "WCWP 10B_023_minimized_cap16.csv"
FILENAME_RE = re.compile(
    r"(?P<course>[A-Z\s]+[0-9A-Z]+)_"  # course code e.g. WCWP 10B
    r"(?P<section>[0-9A-Za-z]+)_"         # section label e.g. 023
    r"minimized_cap(?P<cap>\d+)\.csv" # capacity
)

def connect_db():
    conn = psycopg2.connect(**DB_PARAMS)
    conn.autocommit = False
    return conn

def load_csv_to_db(conn, csv_path, quarter):
    filename = os.path.basename(csv_path)
    match = FILENAME_RE.match(filename)
    if not match:
        print(f"Skipping malformed filename: {filename}")
        return

    course_code = match['course'].strip()
    section_label = match['section']
    capacity = int(match['cap'])

    # Load CSV
    df = pd.read_csv(csv_path)
    if df.empty:
        return

    # Open cursor
    cur = conn.cursor()

    # Try to insert
    cur.execute("""
        INSERT INTO sections (course_code, section_label, quarter, capacity)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (course_code, section_label, quarter) DO NOTHING;
    """, (course_code, section_label, quarter, capacity))

    # Get section_id (always works)
    cur.execute("""
        SELECT section_id
        FROM sections
        WHERE course_code=%s AND section_label=%s AND quarter=%s;
    """, (course_code, section_label, quarter))
    section_id = cur.fetchone()[0]

    # Prepare event rows
    event_rows = [
        (section_id, int(row.time_after_second_pass_seconds), int(row.drops_after))
        for row in df.itertuples(index=False)
    ]

    # Insert events
    cur.executemany("""
        INSERT INTO seat_drop_events (section_id, time_after_second_pass_seconds, drops_after)
        VALUES (%s, %s, %s)
        ON CONFLICT DO NOTHING;
    """, event_rows)

    cur.close()
    print(f"Loaded {len(event_rows)} events from {filename}")

def process_all_csvs():
    conn = connect_db()
    try:
        for year_quarter in os.listdir(CSV_ROOT):
            path_yq = os.path.join(CSV_ROOT, year_quarter)
            if not os.path.isdir(path_yq):
                continue
            for file in os.listdir(path_yq):
                if file.endswith(".csv"):
                    csv_path = os.path.join(path_yq, file)
                    load_csv_to_db(conn, csv_path, year_quarter)
        conn.commit()
    except Exception as e:
        conn.rollback()
        print("Error:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load minimized CSVs into the DB")
    parser.add_argument("--db-password", required=True, help="Postgres user's password")
    parser.add_argument("--csv-root", default=CSV_ROOT, help="Root folder containing CSVs")

    args = parser.parse_args()

    DB_PARAMS["password"] = args.db_password
    CSV_ROOT = args.csv_root

    process_all_csvs()