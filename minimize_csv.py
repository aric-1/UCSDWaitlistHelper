import pandas as pd
from datetime import timedelta
import sys
"""
Utility to minimize section CSV files by extracting seat opening events,
and computing drops_after values; removes extraneous data.
"""


def load_csv(csv_path):
    df = pd.read_csv(csv_path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df

def trim_to_relevant_window(df, instruction_begin, min_waitlist=1):
    """
    Keep only rows after waitlist has started and before instruction_begin + 7 days
    """
    # Detect first time waitlist exists
    waitlist_rows = df[df["waitlisted"] >= min_waitlist]
    if waitlist_rows.empty:
        return pd.DataFrame()
    start_time = waitlist_rows.iloc[0]["time"]
    end_time = instruction_begin + timedelta(days=7)
    return df[(df["time"] >= start_time) & (df["time"] <= end_time)].copy()

def detect_opening_windows(df, min_consecutive=1):
    """
    Identify periods where seats are available for at least min_consecutive samples
    """
    windows = []
    consecutive = 0
    start_time = None
    max_open = 0

    for _, row in df.iterrows():
        if row["available"] > 0:
            consecutive += 1
            max_open = max(max_open, row["available"])
            if consecutive == 1:
                start_time = row["time"]
        else:
            if consecutive >= min_consecutive:
                windows.append((start_time, max_open))
            consecutive = 0
            start_time = None
            max_open = 0

    if consecutive >= min_consecutive:
        windows.append((start_time, max_open))

    return windows

def build_drops_after_series(opening_windows):
    """
    Compute drops_after values as the sum of future openings after each event
    """
    drops_after_list = []
    total = sum(seats for _, seats in opening_windows)

    for t, seats in sorted(opening_windows):
        drops_after_list.append((t, total))
        total -= seats

    return drops_after_list

def minimize_csv(input_csv, instruction_begin_str, output_csv, second_pass_start_str):
    """
    Minimize CSV and record time relative to `second_pass_start_str`.

    Output CSV will contain ONLY these two columns (in this order):
      - `drops_after` (int)
      - `time_after_second_pass_seconds` (float)

    `second_pass_start_str` is required and should be an ISO-8601 UTC datetime string.
    """
    instruction_begin = pd.to_datetime(instruction_begin_str, utc=True)
    second_pass_start = pd.to_datetime(second_pass_start_str, utc=True)

    df = load_csv(input_csv)
    df = trim_to_relevant_window(df, instruction_begin)
    if df.empty:
        print("No relevant waitlist data found.")
        return

    opening_windows = detect_opening_windows(df)
    drops_after = build_drops_after_series(opening_windows)

    # Build DataFrame with only drops_after and seconds-since-second-pass
    # drops_after is a list of (time, total)
    times = pd.to_datetime([t for t, _ in drops_after], utc=True)
    totals = [total for _, total in drops_after]
    time_offsets = (times - second_pass_start).total_seconds()

    out_df = pd.DataFrame({
        "drops_after": totals,
        "time_after_second_pass_seconds": time_offsets,
    })

    out_df.to_csv(output_csv, index=False)
    print(f"Minimized CSV saved to {output_csv}")

# command line testing interface
if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python minimize_csv.py <input_csv> <instruction_begin> <output_csv> <second_pass_start>")
        print("Example: py minimize_csv.py 'BILD 5_A.csv' '2025-01-06T00:00:00Z' 'BILD 5_A_minimized.csv' '2024-11-09T00:00:00Z'")
        sys.exit(1)

    input_csv = sys.argv[1]
    instruction_begin_str = sys.argv[2]
    output_csv = sys.argv[3]
    second_pass_start_str = sys.argv[4]

    minimize_csv(input_csv, instruction_begin_str, output_csv, second_pass_start_str)