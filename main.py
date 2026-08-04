import cv2
import time
import threading
import numpy as np
from datetime import datetime
from database import init_db, get_all_users, sync_unknown_faces
from recognition import get_face_data, recognize, build_embedding_cache
from registration import register_person
from liveness import LivenessDetector
from stability import RecognitionStabilizer
from attendance import try_log_attendance, get_cooldown_remaining, export_to_csv, print_todays_attendance
from unknown_logger import try_log_unknown, print_unknown_summary, update_streak, cleanup_stale_faces as cleanup_unknown_faces

init_db()
sync_unknown_faces()

# ─── Shared state ─────────────────────────────────────────────────────────────
frame_lock        = threading.Lock()
result_lock       = threading.Lock()
latest_frame      = None
latest_full_frame = None
processed_results = []   # (x1,y1,x2,y2, name, conf, data, is_live)
stop_flag         = False
# ─────────────────────────────────────────────────────────────────────────────

users      = get_all_users()
build_embedding_cache(users)
liveness   = LivenessDetector()
stabilizer = RecognitionStabilizer(buffer_size=10, min_votes_to_confirm=5)

prev_face_centers: dict[int, tuple] = {}
next_face_id = 0


def assign_face_ids(boxes):
    global next_face_id, prev_face_centers
    MAX_DIST      = 80
    assigned_ids  = []
    used_existing = set()
    for box in boxes:
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        best_id, best_dist = None, float("inf")
        for fid, (px, py) in prev_face_centers.items():
            if fid in used_existing:
                continue
            dist = np.hypot(cx - px, cy - py)
            if dist < best_dist and dist < MAX_DIST:
                best_dist, best_id = dist, fid
        if best_id is None:
            best_id      = next_face_id
            next_face_id += 1
        assigned_ids.append(best_id)
        used_existing.add(best_id)
        prev_face_centers[best_id] = (cx, cy)
    for fid in list(prev_face_centers.keys()):
        if fid not in used_existing:
            del prev_face_centers[fid]
    return assigned_ids


def processing_thread():
    global latest_frame, latest_full_frame, processed_results, users
    PROCESS_EVERY_N = 3
    frame_count     = 0

    while not stop_flag:
        with frame_lock:
            frame      = latest_frame.copy()      if latest_frame      is not None else None
            full_frame = latest_full_frame.copy() if latest_full_frame is not None else None

        if frame is None:
            time.sleep(0.005)
            continue

        frame_count += 1
        if frame_count % PROCESS_EVERY_N != 0:
            time.sleep(0.001)
            continue

        small             = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        boxes, embeddings = get_face_data(small)
        results           = []

        if boxes is not None:
            scaled_boxes = [[v * 2 for v in box] for box in boxes]
            face_ids     = assign_face_ids(scaled_boxes)
            stabilizer.cleanup_stale_faces(set(face_ids))
            cleanup_unknown_faces(set(face_ids))

            for box, embedding, face_id in zip(scaled_boxes, embeddings, face_ids):
                x1, y1, x2, y2 = [int(v) for v in box]

                liveness.update((x1, y1, x2, y2))
                is_live = liveness.is_live()


                raw_name, raw_conf, data = recognize(embedding)
                stabilizer.update(face_id, raw_name, raw_conf)
                stable_name, stable_conf = stabilizer.get_stable_result(face_id)

                if stable_name != "UNKNOWN":
                    user_id = next((u[0] for u in users if u[1] == stable_name), None)
                    try_log_attendance(user_id, stable_name, stable_conf)
                elif stable_name == "UNKNOWN" and full_frame is not None:
                    # Only log as unknown AFTER stabilizer has enough frames
                    # to be sure this isn't a registered person still being confirmed
                    if stabilizer.is_ready(face_id):
                        try_log_unknown(full_frame, (x1, y1, x2, y2), face_id)

                results.append((x1, y1, x2, y2, stable_name, stable_conf, data, is_live))
        else:
            stabilizer.cleanup_stale_faces(set())
            cleanup_unknown_faces(set())
            prev_face_centers.clear()

        with result_lock:
            processed_results = results


proc_thread = threading.Thread(target=processing_thread, daemon=True)
proc_thread.start()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS,          30)
cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

print("R=register | E=export CSV | T=today attendance | U=unknown log | Q=quit")

fps_counter = 0
fps_display = 0
fps_timer   = time.time()

while True:

    ret, frame = cap.read()
    if not ret:
        break

    with frame_lock:
        latest_frame      = frame.copy()
        latest_full_frame = frame.copy()

    with result_lock:
        current_results = list(processed_results)

    for (x1, y1, x2, y2, name, confidence, data, is_live) in current_results:

        liveness_label = "LIVE" if is_live else "CHECKING"

        if name != "UNKNOWN":
            color = (0, 255, 0) if is_live else (0, 165, 255)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            cv2.putText(frame,
                        f"{name} ({confidence*100:.1f}%) [{liveness_label}]",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
            if data:
                cv2.putText(frame,
                            f"Age: {data['age']}  Mobile: {data['mobile']}",
                            (x1, y2 + 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            cd = get_cooldown_remaining(name)
            if cd > 0:
                cv2.putText(frame, f"Next log in {cd}s",
                            (x1, y2 + 36),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 0), 1)
        else:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(frame, "UNKNOWN [logged]",
                        (x1, y1 - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)

    fps_counter += 1
    if time.time() - fps_timer >= 1.0:
        fps_display = fps_counter
        fps_counter = 0
        fps_timer   = time.time()

    cv2.putText(frame, f"FPS: {fps_display}",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

    cv2.imshow("Recognition System", frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord('r'):
        stop_flag = True
        cap.release()
        cv2.destroyAllWindows()
        reg_name   = input("Name: ")
        reg_age    = input("Age: ")
        reg_mobile = input("Mobile: ")
        success = register_person(reg_name, reg_age, reg_mobile)
        if success:
            users = get_all_users()
            build_embedding_cache(users)
            liveness.reset()
            stabilizer.reset()
            prev_face_centers.clear()
        stop_flag   = False
        proc_thread = threading.Thread(target=processing_thread, daemon=True)
        proc_thread.start()
        cap = cv2.VideoCapture(0)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    elif key == ord('e'):
        export_to_csv()
    elif key == ord('t'):
        print_todays_attendance()
    elif key == ord('u'):
        print_unknown_summary(datetime.now().strftime("%Y-%m-%d"))
    elif key == ord('q'):
        stop_flag = True
        break

cap.release()
cv2.destroyAllWindows()