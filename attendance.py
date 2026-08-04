import time
import csv
import os
from datetime import datetime
from database import insert_attendance, get_attendance

# ── Per-person cooldown ───────────────────────────────────────────────────────
# Prevents the same person being logged every frame.
# Default: 60 seconds between logs for the same person.
COOLDOWN_SECONDS = 60

# name -> last logged timestamp
_last_logged: dict[str, float] = {}
# ─────────────────────────────────────────────────────────────────────────────


def try_log_attendance(user_id: int, name: str, confidence: float) -> bool:
    """
    Log attendance for a recognized person, respecting the cooldown.
    Returns True if a new record was inserted, False if still on cooldown.
    """
    if name == "UNKNOWN" or not name:
        return False

    now = time.time()
    last = _last_logged.get(name, 0)

    if now - last < COOLDOWN_SECONDS:
        return False   # still on cooldown

    insert_attendance(user_id, name, confidence)
    _last_logged[name] = now

    print(f"[Attendance] {name} logged at {datetime.now().strftime('%H:%M:%S')}")
    return True


def get_cooldown_remaining(name: str) -> int:
    """Returns seconds remaining on a person's cooldown (0 if ready)."""
    elapsed = time.time() - _last_logged.get(name, 0)
    remaining = COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))


def export_to_csv(date_str: str = None, output_dir: str = "."):
    """
    Export attendance records to a CSV file.
    date_str: 'YYYY-MM-DD' — if None, exports all records.
    Returns the path to the saved file.
    """
    rows = get_attendance(date_str)

    if not rows:
        print("No attendance records found for the given date.")
        return None

    label     = date_str if date_str else "all"
    filename  = f"attendance_{label}.csv"
    filepath  = os.path.join(output_dir, filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "User ID", "Name", "Confidence (%)", "Timestamp"])
        for row in rows:
            writer.writerow([
                row[0],
                row[1],
                row[2],
                f"{row[3] * 100:.1f}",
                row[4]
            ])

    print(f"[Export] Saved to {filepath}  ({len(rows)} records)")
    return filepath


def print_todays_attendance():
    """Quick terminal summary of today's attendance."""
    today = datetime.now().strftime("%Y-%m-%d")
    rows  = get_attendance(today)

    if not rows:
        print("No attendance recorded today.")
        return

    print(f"\n── Today's Attendance ({today}) ──────────────────")
    print(f"{'Name':<20} {'Confidence':>12}  {'Time'}")
    print("-" * 50)
    for row in rows:
        t = row[4].split(" ")[1][:8] if " " in row[4] else row[4]
        print(f"{row[2]:<20} {row[3]*100:>11.1f}%  {t}")
    print(f"{'Total:':<20} {len(rows)} entries\n")