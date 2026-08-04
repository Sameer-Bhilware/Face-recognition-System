# FaceCore — Real-Time Face Recognition Attendance System

A real-time face recognition attendance system built with **OpenCV**, **PyTorch**, and **FaceNet (InceptionResnetV1)**. It detects and recognizes faces from a live webcam feed, logs attendance automatically, flags unrecognized faces, and ships with a live web dashboard for monitoring everything.

## Features

- **Real-time face detection & recognition** using MTCNN for detection/alignment and a FaceNet (`vggface2`-pretrained InceptionResnetV1) model for embeddings, with cosine-similarity matching against a local database.
- **Multi-threaded pipeline** — capture and recognition run on separate threads so the camera preview stays smooth while recognition runs in the background.
- **Recognition stabilization** — a voting buffer (`RecognitionStabilizer`) across recent frames prevents flickering between names and false positives before a match is confirmed.
- **Basic liveness check** — tracks face-center movement across frames to flag `LIVE` vs `CHECKING`, as a lightweight anti-spoofing signal.
- **Automatic attendance logging** with a per-person cooldown (default 60s) to avoid duplicate entries, plus CSV export.
- **Unknown face logging** — faces that stay unrecognized for a sustained number of frames are cropped, saved to disk, and recorded, with region-based cooldowns to avoid saving the same spot repeatedly.
- **Face re-identification across frames** — a simple centroid-distance tracker assigns stable IDs to faces as they move, so recognition/stabilization state persists per person, per frame.
- **Multi-sample registration** — captures 30 embeddings per person across varied head angles for more robust matching, with duplicate-face detection at registration time.
- **Live web dashboard** (Flask) — view registered users, today's attendance, and unknown-face captures in a browser, with delete actions for both users and unknown face records.

## Tech Stack

| Component | Library |
|---|---|
| Face detection & alignment | MTCNN (`facenet-pytorch`) |
| Face embeddings | InceptionResnetV1, `vggface2` pretrained weights |
| Deep learning backend | PyTorch (CUDA if available, CPU fallback) |
| Camera / rendering | OpenCV |
| Storage | SQLite |
| Dashboard | Flask |

## Project Structure

```
.
├── main.py            # Entry point — camera loop, threading, UI overlay, key bindings
├── models.py           # Loads MTCNN + InceptionResnetV1 (device-aware: CUDA/CPU)
├── recognition.py       # Face detection + embedding extraction + cache-based matching
├── registration.py       # Captures samples for a new user and stores embeddings
├── stability.py          # Frame-buffer voting to stabilize recognized names
├── liveness.py            # Lightweight movement-based liveness detection
├── attendance.py            # Attendance logging, cooldowns, CSV export
├── unknown_logger.py          # Detects, confirms, and saves unrecognized faces
├── database.py                  # SQLite schema + queries (users, attendance, unknown_faces)
├── dashboard.py                    # Flask app serving a live web dashboard
├── utils.py                          # Small embedding helpers
└── requirements.txt
```

## How It Works

1. **Registration** — `registration.py` captures 30 face samples from the webcam across different angles, generates a normalized embedding for each with FaceNet, checks for duplicates against existing users, and stores all embeddings (not just an average) for a given person in SQLite.
2. **Recognition loop** — `main.py` runs a background thread that pulls the latest frame, detects faces with MTCNN, extracts embeddings, and compares them against a pre-built in-memory embedding cache (`recognition.py`) using max cosine similarity per person.
3. **Stabilization** — each detected face is assigned a persistent ID (`assign_face_ids`) based on proximity to faces seen in the previous frame. Raw per-frame recognition results are fed into `RecognitionStabilizer`, which only "confirms" a name once it wins a majority vote across a rolling buffer of frames.
4. **Attendance** — once a face is confirmed, `attendance.py` logs it to SQLite, respecting a per-person cooldown so the same person isn't logged every frame.
5. **Unknown handling** — if a face stays unconfirmed/unknown for a sustained streak of frames (and passes size/warmup/cooldown checks), `unknown_logger.py` crops and saves the face image and records it in the database.
6. **Dashboard** — `dashboard.py` runs a separate Flask server exposing JSON APIs and a single-page dashboard for browsing registered users, attendance history, and unknown face captures, with delete actions for cleanup.

## Setup

### Requirements

- Python 3.9+
- A webcam
- (Recommended) an NVIDIA GPU + CUDA for real-time performance; the code falls back to CPU automatically.

> **Note:** the included `requirements.txt` needs to be regenerated — install the following manually if it's incomplete:

```bash
pip install torch facenet-pytorch opencv-python numpy flask
```

### Run

Start the recognition system:

```bash
python main.py
```

In a separate terminal, start the dashboard:

```bash
python dashboard.py
```

Then open `http://localhost:5000` in your browser.

## Keyboard Controls (main.py)

| Key | Action |
|---|---|
| `R` | Register a new person (pauses the recognition loop) |
| `E` | Export attendance to CSV |
| `T` | Print today's attendance summary to the terminal |
| `U` | Print a summary of logged unknown faces |
| `Q` | Quit |

## Configuration

Key tunable parameters live near the top of their respective files:

- `recognition.py` — `MIN_FACE_SIZE`, `MIN_CONFIDENCE`, `RECOGNITION_THRESHOLD` (cosine similarity cutoff for a match)
- `attendance.py` — `COOLDOWN_SECONDS` (per-person attendance logging cooldown)
- `unknown_logger.py` — `CONFIRM_FRAMES_NEEDED`, `WARMUP_SECONDS`, `COOLDOWN_SECONDS`, `MIN_FACE_SIZE`
- `stability.py` — `buffer_size`, `min_votes_to_confirm` (passed in when constructing `RecognitionStabilizer` in `main.py`)
- `registration.py` — `TARGET_SAMPLES` (embeddings captured per person)

## Known Limitations

- Liveness detection is based purely on face-centroid movement between frames — it's a basic deterrent, not robust anti-spoofing (e.g. it won't reliably catch a moving photo/video).
- Designed for a single local webcam and local SQLite storage; not built for multi-camera or networked deployments out of the box.
- `dashboard.py` runs with Flask's built-in dev server (`debug=True`) — swap in a production WSGI server before deploying anywhere public.

## License

Add a license of your choice (e.g. MIT) before publishing.

##Author

Sameer Bhilware — @Sameer-Bhilware
