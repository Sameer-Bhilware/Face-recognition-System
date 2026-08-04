import cv2
import os
import time
from collections import defaultdict
from datetime import datetime
from database import insert_unknown_face, get_unknown_faces

# ── Config ────────────────────────────────────────────────────────────────────
SAVE_DIR              = "unknown_faces"
COOLDOWN_SECONDS      = 10
MIN_FACE_SIZE         = 80
PADDING               = 20
WARMUP_SECONDS        = 5

# A face must be UNKNOWN for this many consecutive processed frames
# before we even consider saving it. Prevents saving registered people
# who haven't been confirmed yet, and blurry startup frames.
CONFIRM_FRAMES_NEEDED = 15
# ─────────────────────────────────────────────────────────────────────────────

os.makedirs(SAVE_DIR, exist_ok=True)

_start_time  = time.time()
_last_saved: dict[str, float] = {}

# face_id -> consecutive UNKNOWN frame count
_unknown_streak: dict[int, int] = defaultdict(int)


def update_streak(face_id: int, is_unknown: bool):
    """
    Call every processing frame for every detected face.
    Increments streak if unknown, resets to 0 the moment a name is confirmed.
    This prevents a registered person from ever reaching CONFIRM_FRAMES_NEEDED.
    """
    if is_unknown:
        _unknown_streak[face_id] += 1
    else:
        # Known person confirmed — hard reset so they can never be logged
        _unknown_streak[face_id] = 0


def is_confirmed_unknown(face_id: int) -> bool:
    """Returns True only after sustained consecutive UNKNOWN frames."""
    return _unknown_streak.get(face_id, 0) >= CONFIRM_FRAMES_NEEDED


def cleanup_stale_faces(active_ids: set):
    for fid in list(_unknown_streak.keys()):
        if fid not in active_ids:
            del _unknown_streak[fid]


def _region_key(x1: int, y1: int, frame_w: int, frame_h: int) -> str:
    col = int((x1 / frame_w) * 4)
    row = int((y1 / frame_h) * 3)
    return f"{col}_{row}"


def try_log_unknown(frame, box: tuple, face_id: int) -> bool:
    """
    Save an unknown face only when ALL conditions are met:
    1. Warmup period passed (camera focused)
    2. Face box is large enough
    3. Face has been UNKNOWN for CONFIRM_FRAMES_NEEDED consecutive frames
    4. Region cooldown has expired
    """
    # 1. Warmup
    if (time.time() - _start_time) < WARMUP_SECONDS:
        return False

    # 2. Size filter
    x1, y1, x2, y2 = [int(v) for v in box]
    if (x2 - x1) < MIN_FACE_SIZE or (y2 - y1) < MIN_FACE_SIZE:
        return False

    # 3. Must be confirmed unknown — not just momentarily unrecognized
    if not is_confirmed_unknown(face_id):
        return False

    # 4. Region cooldown
    frame_h, frame_w = frame.shape[:2]
    key  = _region_key(x1, y1, frame_w, frame_h)
    now  = time.time()
    if now - _last_saved.get(key, 0) < COOLDOWN_SECONDS:
        return False

    # Crop and save
    cropped = frame[
        max(0, y1 - PADDING) : min(frame_h, y2 + PADDING),
        max(0, x1 - PADDING) : min(frame_w, x2 + PADDING)
    ]
    if cropped.size == 0:
        return False

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
    filepath = os.path.join(SAVE_DIR, f"unknown_{ts}.jpg")

    cv2.imwrite(filepath, cropped)
    insert_unknown_face(filepath)
    _last_saved[key] = now

    print(f"[Unknown] Confirmed & saved → {filepath}")
    return True


def print_unknown_summary(date_str: str = None):
    rows  = get_unknown_faces(date_str)
    label = date_str if date_str else "all time"
    print(f"\n── Unknown Faces ({label}) ──────────────────────")
    if not rows:
        print("  No unknown faces logged.")
    else:
        print(f"{'ID':<6} {'Timestamp':<22} {'Image Path'}")
        print("-" * 60)
        for row in rows:
            print(f"{row[0]:<6} {row[2]:<22} {row[1]}")
        print(f"\nTotal: {len(rows)} unknown face(s) logged.\n")