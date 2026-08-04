import cv2
import torch
import json
import numpy as np
import torch.nn.functional as F
from models import mtcnn, resnet, device
from database import insert_user, get_all_users


def preprocess_check(embeddings_list: list) -> torch.Tensor:
    avg    = np.mean(embeddings_list, axis=0)
    tensor = torch.tensor(avg, dtype=torch.float32).unsqueeze(0).to(device)
    return F.normalize(tensor, p=2, dim=1)


def check_duplicate(new_embedding: torch.Tensor, threshold=0.75) -> tuple[bool, str, float]:
    users = get_all_users()
    if not users:
        return False, "", 0.0

    best_score = -1.0
    best_name  = ""

    for user in users:
        name            = user[1]
        embeddings_json = user[4]
        stored          = json.loads(embeddings_json)
        stored_tensor   = torch.tensor(stored, dtype=torch.float32).to(device)
        stored_tensor   = F.normalize(stored_tensor, p=2, dim=1)
        similarity      = F.cosine_similarity(new_embedding, stored_tensor)
        score           = similarity.max().item()

        if score > best_score:
            best_score = score
            best_name  = name

    if best_score >= threshold:
        return True, best_name, best_score

    return False, "", best_score


def register_person(name, age, mobile):
    cap = cv2.VideoCapture(0)
    print("Capturing 30 samples... Slowly turn head left, right, tilt up and down.")
    print("More varied angles = much better recognition accuracy.\n")

    embeddings_list = []
    samples         = 0
    TARGET_SAMPLES  = 30   # increased from 20 — more angles = more robust

    while samples < TARGET_SAMPLES:
        ret, frame = cap.read()
        if not ret:
            continue

        boxes, _ = mtcnn.detect(frame)

        if boxes is not None:
            faces = mtcnn.extract(frame, boxes, save_path=None)
            if faces is not None:
                face = faces[0].unsqueeze(0).to(device)

                with torch.inference_mode():
                    if device.type == 'cuda':
                        with torch.amp.autocast('cuda'):
                            embedding = resnet(face)
                    else:
                        embedding = resnet(face)
                    embedding = F.normalize(embedding, p=2, dim=1)

                embeddings_list.append(embedding[0].cpu().tolist())
                samples += 1
                print(f"Captured {samples}/{TARGET_SAMPLES}")

                x1, y1, x2, y2 = [int(v) for v in boxes[0]]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, f"Capturing {samples}/{TARGET_SAMPLES}",
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Registering - Press Q to cancel", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    if len(embeddings_list) == 0:
        print("Registration failed: no faces captured.")
        return False

    # Duplicate check
    new_embedding = preprocess_check(embeddings_list)
    is_dup, matched_name, score = check_duplicate(new_embedding)
    if is_dup:
        print(f"\n⚠  Duplicate detected!")
        print(f"   This face closely matches '{matched_name}' ({score*100:.1f}%)")
        print("   Registration cancelled.\n")
        return False

    # ── Store ALL embeddings, not just the average ────────────────────────────
    # Keeping individual embeddings means recognition uses .max() similarity
    # across all angles — a side-profile captured during registration will
    # correctly match a side-profile seen during recognition.
    # We keep every embedding (30 vectors) instead of collapsing to 1.
    embeddings_json = json.dumps(embeddings_list)
    # ─────────────────────────────────────────────────────────────────────────

    insert_user(name, age, mobile, embeddings_json)
    print(f"\n✅ Registration successful for {name} ({len(embeddings_list)} embeddings stored).\n")
    return True