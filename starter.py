import pandas as pd
from datetime import datetime, timedelta
from typing import Optional


def parse_time(ts: str) -> pd.Timestamp:
    return pd.to_datetime(ts, utc=True)


def load_section_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.sort_values("time").reset_index(drop=True)
    return df


def compute_seat_openings(
    df: pd.DataFrame,
    query_time: datetime,
    instruction_begin: datetime,
    min_consecutive_samples: int = 2,
):
    """
    Returns seat opening stats from query_time until
    7 days after instruction begins.
    """

    end_time = instruction_begin + timedelta(days=7)

    # Filter time window
    mask = (df["time"] >= query_time) & (df["time"] <= end_time)
    window = df.loc[mask].copy()

    if window.empty:
        return {
            "total_seats_opened": 0,
            "opening_windows": 0,
            "first_open_time": None,
            "last_open_time": None,
        }

    # Boolean: seats available
    window["open"] = window["available"] > 0

    opening_windows = []
    current_start = None
    current_max = 0
    consecutive = 0

    for _, row in window.iterrows():
        if row["open"]:
            consecutive += 1
            current_max = max(current_max, row["available"])

            if consecutive == 1:
                current_start = row["time"]

        else:
            if consecutive >= min_consecutive_samples:
                opening_windows.append(
                    {
                        "start": current_start,
                        "max_open_seats": current_max,
                    }
                )

            # reset
            consecutive = 0
            current_start = None
            current_max = 0

    # Handle trailing window
    if consecutive >= min_consecutive_samples:
        opening_windows.append(
            {
                "start": current_start,
                "max_open_seats": current_max,
            }
        )

    total_seats_opened = sum(w["max_open_seats"] for w in opening_windows)

    return {
        "total_seats_opened": total_seats_opened,
        "opening_windows": len(opening_windows),
        "first_open_time": opening_windows[0]["start"] if opening_windows else None,
        "last_open_time": opening_windows[-1]["start"] if opening_windows else None,
    }


if __name__ == "__main__":
    # ---- CONFIG ----
    CSV_PATH = "BILD 5_A.csv"

    QUERY_TIME = parse_time("2025-01-02T12:00:00")
    INSTRUCTION_BEGIN = parse_time("2025-01-06T00:00:00")

    # ---- RUN ----
    df = load_section_csv(CSV_PATH)
    result = compute_seat_openings(
        df,
        query_time=QUERY_TIME,
        instruction_begin=INSTRUCTION_BEGIN,
    )

    print("Seat opening results:")
    for k, v in result.items():
        print(f"{k}: {v}")