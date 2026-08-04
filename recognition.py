import torch
import torch.nn.functional as F
import json
import numpy as np
from models import mtcnn, resnet, device

# ── Thresholds ────────────────────────────────────────────────────────────────
MIN_FACE_SIZE         = 80
MIN_CONFIDENCE        = 0.92
RECOGNITION_THRESHOLD = 0.68
# ─────────────────────────────────────────────────────────────────────────────

# ── Embedding cache ───────────────────────────────────────────────────────────
# Pre-built once from DB rows, reused every frame.
# Structure: list of (name, age, mobile, tensor[N x 512])
_embedding_cache: list[tuple] = []


def build_embedding_cache(users: list):
    """
    Call once at startup and after every new registration.
    Converts all stored JSON embeddings into normalised GPU tensors
    so recognition never touches JSON or numpy at runtime.
    """
    global _embedding_cache
    _embedding_cache = []

    for user in users:
        name            = user[1]
        age             = user[2]
        mobile          = user[3]
        embeddings_json = user[4]

        stored_list   = json.loads(embeddings_json)
        tensor        = torch.tensor(stored_list, dtype=torch.float32).to(device)
        tensor        = F.normalize(tensor, p=2, dim=1)   # shape: [N, 512]

        _embedding_cache.append((name, age, mobile, tensor))

    print(f"[Cache] Built embedding cache for {len(_embedding_cache)} user(s).")
# ─────────────────────────────────────────────────────────────────────────────


def get_face_data(frame):
    boxes, probs = mtcnn.detect(frame)

    if boxes is None:
        return None, None

    # Filter by confidence and size in one pass
    mask = []
    for box, prob in zip(boxes, probs):
        if prob is None or prob < MIN_CONFIDENCE:
            mask.append(False)
            continue
        x1, y1, x2, y2 = box
        mask.append((x2 - x1) >= MIN_FACE_SIZE and (y2 - y1) >= MIN_FACE_SIZE)

    filtered = boxes[mask]
    if len(filtered) == 0:
        return None, None

    faces = mtcnn.extract(frame, filtered, save_path=None)
    if faces is None:
        return None, None

    faces = faces.to(device)

    with torch.inference_mode():
        if device.type == 'cuda':
            with torch.amp.autocast('cuda'):
                embeddings = resnet(faces)
        else:
            embeddings = resnet(faces)
        embeddings = F.normalize(embeddings, p=2, dim=1)

    return filtered, embeddings


def recognize(embedding):
    """
    Recognize a single face embedding against the pre-built cache.
    No JSON parsing, no tensor construction — pure matrix ops every call.
    """
    if not _embedding_cache:
        return "UNKNOWN", 0.0, None

    best_match = "UNKNOWN"
    best_score = -1.0
    best_data  = None

    # Single expanded query vector compared against each user's full matrix
    query = embedding.unsqueeze(0)   # [1, 512]

    for name, age, mobile, stored_tensor in _embedding_cache:
        # stored_tensor: [N, 512] — one row per captured sample
        sims  = F.cosine_similarity(query.expand(stored_tensor.shape[0], -1),
                                    stored_tensor)
        score = sims.max().item()

        if score > best_score:
            best_score = score
            best_match = name
            best_data  = {"name": name, "age": age, "mobile": mobile}

    if best_score < RECOGNITION_THRESHOLD:
        return "UNKNOWN", best_score, None

    return best_match, best_score, best_data