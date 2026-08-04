import sqlite3

DB_PATH = "face_database.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age TEXT,
            mobile TEXT,
            embeddings TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER,
            name       TEXT,
            confidence REAL,
            timestamp  DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ── Unknown faces table ───────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS unknown_faces (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # ─────────────────────────────────────────────────────────────────────────

    conn.commit()
    conn.close()


def insert_user(name, age, mobile, embeddings_json):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (name, age, mobile, embeddings) VALUES (?, ?, ?, ?)",
        (name, age, mobile, embeddings_json)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return users


def insert_attendance(user_id: int, name: str, confidence: float):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO attendance (user_id, name, confidence) VALUES (?, ?, ?)",
        (user_id, name, round(confidence, 4))
    )
    conn.commit()
    conn.close()


def get_attendance(date_str: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if date_str:
        cursor.execute(
            "SELECT * FROM attendance WHERE DATE(timestamp) = ? ORDER BY timestamp DESC",
            (date_str,)
        )
    else:
        cursor.execute("SELECT * FROM attendance ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def insert_unknown_face(image_path: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO unknown_faces (image_path) VALUES (?)",
        (image_path,)
    )
    conn.commit()
    conn.close()


def get_unknown_faces(date_str: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if date_str:
        cursor.execute(
            "SELECT * FROM unknown_faces WHERE DATE(timestamp) = ? ORDER BY timestamp DESC",
            (date_str,)
        )
    else:
        cursor.execute("SELECT * FROM unknown_faces ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows


def sync_unknown_faces():
    """
    Remove DB records whose image files no longer exist on disk.
    Call this on startup so manually deleted files (e.g. via VS Code)
    don't leave behind orphaned records and broken dashboard images.
    """
    import os
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, image_path FROM unknown_faces")
    rows   = cursor.fetchall()

    removed = 0
    for record_id, image_path in rows:
        if not os.path.exists(image_path):
            cursor.execute("DELETE FROM unknown_faces WHERE id = ?", (record_id,))
            removed += 1

    conn.commit()
    conn.close()

    if removed:
        print(f"[DB Sync] Removed {removed} orphaned unknown face record(s).")