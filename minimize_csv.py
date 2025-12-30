import pandas as pd
from datetime import timedelta
import sys
from pathlib import Path
"""
Utility to minimize section CSV files by extracting seat opening events,
and computing drops_after values; removes extraneous data.
"""


def load_csv(csv_path):
    df = pd.read_csv(csv_path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    return df

def trim_to_relevant_window(df, instruction_begin, waitlist_close, min_waitlist=1):
    """
    Keep only rows after waitlist has started and before `waitlist_close`.

    `waitlist_close` should be a timestamp (timezone-aware) representing when the waitlist
    is considered closed for the section (inclusive).
    """
    # Detect first time waitlist exists
    waitlist_rows = df[df["waitlisted"] >= min_waitlist]
    if waitlist_rows.empty:
        return pd.DataFrame()
    start_time = waitlist_rows.iloc[0]["time"]
    end_time = waitlist_close
    return df[(df["time"] >= start_time) & (df["time"] <= end_time)].copy()

def detect_opening_windows(df):
    """
    Record every instance when `available` increases between consecutive samples.

    Returns a list of tuples (time, seats_opened) where `time` is the timestamp of the
    row where the increase was observed and `seats_opened` == current_available - previous_available.

    Also includes an initial entry (first_time, 0) to indicate the start of the window.
    """
    # sort by time and handle empty data
    df_sorted = df.sort_values("time")
    if df_sorted.empty:
        return []

    windows = []

    # initialize with the first row
    first_row = df_sorted.iloc[0]
    windows.append((first_row["time"], 0))
    try:
        prev_avail = int(first_row["available"])
    except Exception:
        prev_avail = None

    # iterate remaining rows
    for _, row in df_sorted.iloc[1:].iterrows():
        if "available" not in row:
            continue
        try:
            avail = int(row["available"])
        except Exception:
            prev_avail = None
            continue

        if prev_avail is None:
            prev_avail = avail
            continue

        if avail > prev_avail:
            windows.append((row["time"], avail - prev_avail))

        prev_avail = avail

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

def minimize_csv(input_csv, instruction_begin_str, output_csv, second_pass_start_str, waitlist_close_str):
    """
    Minimize CSV and record time relative to `second_pass_start_str`.

    Output CSV will contain ONLY these two columns (in this order):
      - `drops_after` (int)
      - `time_after_second_pass_seconds` (float)

    Both `second_pass_start_str` and `waitlist_close_str` are required and should be
    ISO-8601 UTC datetime strings.
    """
    instruction_begin = pd.to_datetime(instruction_begin_str, utc=True)
    second_pass_start = pd.to_datetime(second_pass_start_str, utc=True)
    waitlist_close = pd.to_datetime(waitlist_close_str, utc=True)

    df = load_csv(input_csv)
    df = trim_to_relevant_window(df, instruction_begin, waitlist_close)
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

    # determine ending capacity at or before waitlist_close
    ending_capacity = None
    if "total" in df.columns:
        # rows up to and including waitlist_close
        rows_up_to_close = df[df["time"] <= waitlist_close]
        if not rows_up_to_close.empty:
            try:
                ending_capacity = int(rows_up_to_close.iloc[-1]["total"])
            except Exception:
                ending_capacity = None

    # append capacity to output filename
    out_path = Path(output_csv)
    cap_suffix = f"_cap{ending_capacity}" if ending_capacity is not None else "_capNA"
    final_out_path = out_path.with_name(out_path.stem + cap_suffix + out_path.suffix)

    out_df.to_csv(final_out_path, index=False)
    print(f"Minimized CSV saved to {final_out_path} (ending_capacity={ending_capacity})")

    return str(final_out_path), ending_capacity

# command line testing interface
if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("Usage: python minimize_csv.py <input_csv> <instruction_begin> <output_csv> <second_pass_start> <waitlist_close>")
        print("Example: py minimize_csv.py 'BILD 5_A.csv' '2025-01-06T00:00:00Z' 'BILD 5_A_minimized.csv' '2024-11-19T00:00:00Z' '2025-01-16T00:00:00Z'")
        sys.exit(1)

    input_csv = sys.argv[1]
    instruction_begin_str = sys.argv[2]
    output_csv = sys.argv[3]
    second_pass_start_str = sys.argv[4]
    waitlist_close_str = sys.argv[5]

    minimize_csv(input_csv, instruction_begin_str, output_csv, second_pass_start_str, waitlist_close_str)