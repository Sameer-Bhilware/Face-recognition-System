from flask import Flask, jsonify, send_from_directory, request
from database import get_all_users, get_attendance, get_unknown_faces, sync_unknown_faces
from datetime import datetime
import os
import sqlite3

app = Flask(__name__)
DB_PATH = "face_database.db"

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FaceCore — Recognition Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg:        #0a0a0f;
    --surface:   #111118;
    --surface2:  #1a1a24;
    --border:    #ffffff12;
    --accent:    #00ff88;
    --accent2:   #00c8ff;
    --danger:    #ff4466;
    --warn:      #ffaa00;
    --text:      #e8e8f0;
    --muted:     #6b6b80;
    --glow:      0 0 24px #00ff8844;
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Mono', monospace;
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ── Grid background ───────────────────────────────────── */
  body::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
      linear-gradient(var(--border) 1px, transparent 1px),
      linear-gradient(90deg, var(--border) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none;
    z-index: 0;
  }

  /* ── Layout ─────────────────────────────────────────────── */
  .shell { position: relative; z-index: 1; }

  header {
    padding: 28px 40px;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
    backdrop-filter: blur(12px);
    background: #0a0a0f99;
    position: sticky; top: 0; z-index: 100;
  }

  .logo {
    font-family: 'Syne', sans-serif;
    font-weight: 800;
    font-size: 1.4rem;
    letter-spacing: -0.03em;
    display: flex; align-items: center; gap: 10px;
  }
  .logo-dot {
    width: 10px; height: 10px;
    background: var(--accent);
    border-radius: 50%;
    box-shadow: var(--glow);
    animation: pulse 2s infinite;
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 1; }
    50%       { transform: scale(1.4); opacity: 0.6; }
  }

  .header-right {
    display: flex; align-items: center; gap: 20px;
  }
  .live-badge {
    font-size: 0.65rem;
    font-weight: 500;
    color: var(--accent);
    border: 1px solid var(--accent);
    padding: 4px 10px;
    border-radius: 2px;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }
  .date-display {
    font-size: 0.7rem;
    color: var(--muted);
    letter-spacing: 0.05em;
  }

  /* ── Stat cards ──────────────────────────────────────────── */
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1px;
    border: 1px solid var(--border);
    margin: 32px 40px;
    background: var(--border);
  }

  .stat-card {
    background: var(--surface);
    padding: 28px 24px;
    position: relative;
    overflow: hidden;
    transition: background 0.2s;
  }
  .stat-card:hover { background: var(--surface2); }
  .stat-card::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 2px;
    background: var(--accent-color, var(--accent));
    transform: scaleX(0);
    transition: transform 0.3s;
    transform-origin: left;
  }
  .stat-card:hover::after { transform: scaleX(1); }

  .stat-label {
    font-size: 0.62rem;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }
  .stat-value {
    font-family: 'Syne', sans-serif;
    font-size: 2.8rem;
    font-weight: 800;
    line-height: 1;
    color: var(--accent-color, var(--accent));
  }
  .stat-sub {
    font-size: 0.62rem;
    color: var(--muted);
    margin-top: 8px;
  }

  /* ── Main content ────────────────────────────────────────── */
  .content { padding: 0 40px 60px; }

  /* ── Tabs ────────────────────────────────────────────────── */
  .tabs {
    display: flex;
    gap: 2px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 28px;
  }
  .tab {
    font-family: 'Syne', sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 14px 24px;
    cursor: pointer;
    color: var(--muted);
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
    background: none; border-top: none; border-left: none; border-right: none;
  }
  .tab:hover { color: var(--text); }
  .tab.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }

  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  /* ── Section header ──────────────────────────────────────── */
  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
  }
  .section-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
  }

  /* ── Date picker ─────────────────────────────────────────── */
  .date-picker {
    background: var(--surface2);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 7px 14px;
    font-family: 'DM Mono', monospace;
    font-size: 0.72rem;
    cursor: pointer;
    outline: none;
    transition: border-color 0.2s;
  }
  .date-picker:focus { border-color: var(--accent); }

  /* ── Table ───────────────────────────────────────────────── */
  .table-wrap {
    border: 1px solid var(--border);
    overflow: hidden;
  }
  table { width: 100%; border-collapse: collapse; }
  thead tr {
    background: var(--surface2);
    border-bottom: 1px solid var(--border);
  }
  th {
    font-size: 0.6rem;
    font-weight: 500;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    padding: 12px 16px;
    text-align: left;
  }
  tbody tr {
    border-bottom: 1px solid var(--border);
    transition: background 0.15s;
  }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: var(--surface2); }
  td {
    padding: 13px 16px;
    font-size: 0.75rem;
    color: var(--text);
  }

  .badge {
    display: inline-block;
    padding: 3px 8px;
    font-size: 0.6rem;
    letter-spacing: 0.08em;
    border-radius: 2px;
    font-weight: 500;
  }
  .badge-green  { background: #00ff8820; color: var(--accent); }
  .badge-blue   { background: #00c8ff20; color: var(--accent2); }
  .badge-red    { background: #ff446620; color: var(--danger); }

  .conf-bar {
    display: flex; align-items: center; gap: 10px;
  }
  .conf-track {
    flex: 1; height: 3px;
    background: var(--surface2);
    border-radius: 2px;
    overflow: hidden;
  }
  .conf-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .conf-val { font-size: 0.68rem; color: var(--muted); min-width: 36px; }

  /* ── Delete button ───────────────────────────────────────── */
  .btn-del {
    background: none;
    border: 1px solid #ff446640;
    color: var(--danger);
    padding: 5px 12px;
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    cursor: pointer;
    letter-spacing: 0.05em;
    transition: all 0.2s;
  }
  .btn-del:hover {
    background: #ff446620;
    border-color: var(--danger);
  }

  /* ── Unknown images grid ─────────────────────────────────── */
  .img-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 12px;
  }
  .img-card {
    background: var(--surface);
    border: 1px solid var(--border);
    overflow: hidden;
    transition: border-color 0.2s, transform 0.2s;
    cursor: pointer;
  }
  .img-card:hover {
    border-color: var(--danger);
    transform: translateY(-2px);
  }
  .img-card img {
    width: 100%; aspect-ratio: 1;
    object-fit: cover; display: block;
    filter: grayscale(20%);
    transition: filter 0.2s;
  }
  .img-card:hover img { filter: grayscale(0%); }
  .img-card-meta {
    padding: 8px 10px;
    font-size: 0.58rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .btn-del-img {
    background: none;
    border: none;
    color: var(--danger);
    font-size: 0.7rem;
    cursor: pointer;
    padding: 0 2px;
    line-height: 1;
    opacity: 0.5;
    transition: opacity 0.2s;
  }
  .btn-del-img:hover { opacity: 1; }

  /* ── Empty state ─────────────────────────────────────────── */
  .empty {
    padding: 60px 0;
    text-align: center;
    color: var(--muted);
    font-size: 0.75rem;
    letter-spacing: 0.05em;
    border: 1px solid var(--border);
  }
  .empty-icon { font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }

  /* ── Loading skeleton ────────────────────────────────────── */
  @keyframes shimmer {
    0%   { background-position: -600px 0; }
    100% { background-position: 600px 0; }
  }
  .skeleton {
    background: linear-gradient(90deg, var(--surface) 25%, var(--surface2) 50%, var(--surface) 75%);
    background-size: 600px 100%;
    animation: shimmer 1.4s infinite;
    border-radius: 2px;
    height: 14px;
  }

  /* ── Lightbox ────────────────────────────────────────────── */
  .lightbox {
    display: none;
    position: fixed; inset: 0; z-index: 999;
    background: #000000cc;
    align-items: center; justify-content: center;
    backdrop-filter: blur(8px);
  }
  .lightbox.open { display: flex; }
  .lightbox img {
    max-width: 80vw; max-height: 80vh;
    border: 1px solid var(--border);
    box-shadow: 0 0 60px #000;
  }
  .lightbox-close {
    position: fixed; top: 24px; right: 32px;
    font-size: 2rem; color: var(--muted);
    cursor: pointer; transition: color 0.2s;
  }
  .lightbox-close:hover { color: var(--text); }

  /* ── Refresh btn ─────────────────────────────────────────── */
  .btn-refresh {
    background: none;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 7px 14px;
    font-family: 'DM Mono', monospace;
    font-size: 0.65rem;
    cursor: pointer;
    letter-spacing: 0.05em;
    transition: all 0.2s;
  }
  .btn-refresh:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  /* ── Scrollbar ───────────────────────────────────────────── */
  ::-webkit-scrollbar { width: 4px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); }

  @media (max-width: 900px) {
    .stats-row { grid-template-columns: repeat(2, 1fr); }
    header, .content, .stats-row { padding-left: 20px; padding-right: 20px; }
    .stats-row { margin-left: 20px; margin-right: 20px; }
  }
</style>
</head>
<body>
<div class="shell">

  <!-- Header -->
  <header>
    <div class="logo">
      <div class="logo-dot"></div>
      FaceCore
    </div>
    <div class="header-right">
      <span class="live-badge">● Live</span>
      <span class="date-display" id="headerDate"></span>
    </div>
  </header>

  <!-- Stats -->
  <div class="stats-row">
    <div class="stat-card" style="--accent-color: var(--accent)">
      <div class="stat-label">Registered Users</div>
      <div class="stat-value" id="statUsers">—</div>
      <div class="stat-sub">total in database</div>
    </div>
    <div class="stat-card" style="--accent-color: var(--accent2)">
      <div class="stat-label">Present Today</div>
      <div class="stat-value" id="statPresent">—</div>
      <div class="stat-sub">unique faces seen</div>
    </div>
    <div class="stat-card" style="--accent-color: var(--warn)">
      <div class="stat-label">Attendance Logs</div>
      <div class="stat-value" id="statLogs">—</div>
      <div class="stat-sub">entries today</div>
    </div>
    <div class="stat-card" style="--accent-color: var(--danger)">
      <div class="stat-label">Unknown Faces</div>
      <div class="stat-value" id="statUnknown">—</div>
      <div class="stat-sub">captured today</div>
    </div>
  </div>

  <!-- Tabs + Content -->
  <div class="content">
    <div class="tabs">
      <button class="tab active" onclick="switchTab('users')">Registered Users</button>
      <button class="tab" onclick="switchTab('attendance')">Attendance</button>
      <button class="tab" onclick="switchTab('unknown')">Unknown Faces</button>
    </div>

    <!-- Users Panel -->
    <div class="tab-panel active" id="panel-users">
      <div class="section-header">
        <span class="section-title">All Registered Users</span>
        <button class="btn-refresh" onclick="loadUsers()">↻ Refresh</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Age</th>
              <th>Mobile</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody id="usersTable"></tbody>
        </table>
      </div>
    </div>

    <!-- Attendance Panel -->
    <div class="tab-panel" id="panel-attendance">
      <div class="section-header">
        <span class="section-title">Attendance Log</span>
        <div style="display:flex;gap:10px;align-items:center">
          <input type="date" class="date-picker" id="attDate" onchange="loadAttendance()">
          <button class="btn-refresh" onclick="loadAttendance()">↻ Refresh</button>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Confidence</th>
              <th>Time</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody id="attTable"></tbody>
        </table>
      </div>
    </div>

    <!-- Unknown Faces Panel -->
    <div class="tab-panel" id="panel-unknown">
      <div class="section-header">
        <span class="section-title">Unknown Face Log</span>
        <div style="display:flex;gap:10px;align-items:center">
          <input type="date" class="date-picker" id="unkDate" onchange="loadUnknown()">
          <button class="btn-refresh" onclick="loadUnknown()">↻ Refresh</button>
        </div>
      </div>
      <div id="unknownGrid"></div>
    </div>

  </div>
</div>

<!-- Lightbox -->
<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">✕</span>
  <img id="lightboxImg" src="" alt="">
</div>

<script>
  // ── Init ─────────────────────────────────────────────────────────────────
  const today = new Date().toISOString().split("T")[0];
  document.getElementById("headerDate").textContent = new Date().toLocaleDateString("en-IN", {
    weekday: "long", year: "numeric", month: "long", day: "numeric"
  });
  document.getElementById("attDate").value = today;
  document.getElementById("unkDate").value = today;

  loadStats();
  loadUsers();
  loadAttendance();
  loadUnknown();

  // Auto-refresh stats every 10s
  setInterval(loadStats, 10000);

  // ── Tab switching ─────────────────────────────────────────────────────────
  function switchTab(name) {
    document.querySelectorAll(".tab").forEach((t, i) => {
      const names = ["users", "attendance", "unknown"];
      t.classList.toggle("active", names[i] === name);
    });
    document.querySelectorAll(".tab-panel").forEach(p => {
      p.classList.toggle("active", p.id === "panel-" + name);
    });
  }

  // ── Stats ─────────────────────────────────────────────────────────────────
  async function loadStats() {
    const d = await fetch("/api/stats").then(r => r.json());
    animateCount("statUsers",   d.total_registered);
    animateCount("statPresent", d.present_today);
    animateCount("statLogs",    d.attendance_logs);
    animateCount("statUnknown", d.unknown_today);
  }

  function animateCount(id, target) {
    const el  = document.getElementById(id);
    const cur = parseInt(el.textContent) || 0;
    const diff = target - cur;
    if (diff === 0) return;
    let step = 0;
    const steps = 20;
    const timer = setInterval(() => {
      step++;
      el.textContent = Math.round(cur + (diff * step / steps));
      if (step >= steps) clearInterval(timer);
    }, 18);
  }

  // ── Users ─────────────────────────────────────────────────────────────────
  async function loadUsers() {
    const users = await fetch("/api/users").then(r => r.json());
    const tbody = document.getElementById("usersTable");
    if (!users.length) {
      tbody.innerHTML = `<tr><td colspan="6">
        <div class="empty"><div class="empty-icon">👤</div>No users registered yet.</div>
      </td></tr>`;
      return;
    }
    tbody.innerHTML = users.map(u => `
      <tr>
        <td><span class="badge badge-blue">${String(u.id).padStart(3,"0")}</span></td>
        <td style="font-family:'Syne',sans-serif;font-weight:600">${u.name}</td>
        <td>${u.age}</td>
        <td>${u.mobile}</td>
        <td><span class="badge badge-green">REGISTERED</span></td>
        <td>
          <button class="btn-del" onclick="deleteUser(${u.id}, '${u.name}')">DELETE</button>
        </td>
      </tr>
    `).join("");
  }

  async function deleteUser(id, name) {
    if (!confirm(`Remove ${name} from the database?`)) return;
    await fetch("/api/delete_user/" + id, { method: "DELETE" });
    loadUsers();
    loadStats();
  }

  // ── Attendance ────────────────────────────────────────────────────────────
  async function loadAttendance() {
    const date = document.getElementById("attDate").value;
    const rows = await fetch("/api/attendance?date=" + date).then(r => r.json());
    const tbody = document.getElementById("attTable");
    if (!rows.length) {
      tbody.innerHTML = `<tr><td colspan="5">
        <div class="empty"><div class="empty-icon">📋</div>No attendance records for this date.</div>
      </td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((r, i) => `
      <tr>
        <td style="color:var(--muted)">${i + 1}</td>
        <td style="font-family:'Syne',sans-serif;font-weight:600">${r.name}</td>
        <td>
          <div class="conf-bar">
            <div class="conf-track">
              <div class="conf-fill" style="width:${r.confidence}%"></div>
            </div>
            <span class="conf-val">${r.confidence}%</span>
          </div>
        </td>
        <td style="color:var(--muted)">${r.timestamp.split(" ")[1] || r.timestamp}</td>
        <td><span class="badge badge-green">PRESENT</span></td>
      </tr>
    `).join("");
  }

  // ── Unknown faces ─────────────────────────────────────────────────────────
  async function loadUnknown() {
    const date  = document.getElementById("unkDate").value;
    const rows  = await fetch("/api/unknown?date=" + date).then(r => r.json());
    const grid  = document.getElementById("unknownGrid");
    if (!rows.length) {
      grid.innerHTML = `<div class="empty"><div class="empty-icon">🔍</div>No unknown faces logged for this date.</div>`;
      return;
    }
    grid.innerHTML = `<div class="img-grid">${
      rows.map(r => {
        const fname = r.image_path.replace(/\\\\/g, "/").split("/").pop();
        const time  = r.timestamp.split(" ")[1]?.slice(0,8) || "";
        return `
          <div class="img-card" id="unk-${r.id}">
            <img src="/unknown_faces/${fname}" alt="Unknown" loading="lazy"
                 onerror="this.style.display='none'"
                 onclick="openLightbox('/unknown_faces/${fname}')" style="cursor:pointer">
            <div class="img-card-meta">
              <span>${time}</span>
              <button class="btn-del-img" title="Delete" onclick="deleteUnknown(${r.id})">✕</button>
            </div>
          </div>`;
      }).join("")
    }</div>`;
  }

  // ── Lightbox ──────────────────────────────────────────────────────────────
  async function deleteUnknown(id) {
    if (!confirm("Delete this unknown face image?")) return;
    await fetch("/api/delete_unknown/" + id, { method: "DELETE" });
    const el = document.getElementById("unk-" + id);
    if (el) {
      el.style.transition = "opacity 0.3s, transform 0.3s";
      el.style.opacity    = "0";
      el.style.transform  = "scale(0.8)";
      setTimeout(() => { el.remove(); loadStats(); }, 300);
    }
  }

  function openLightbox(src) {
    document.getElementById("lightboxImg").src = src;
    document.getElementById("lightbox").classList.add("open");
  }
  function closeLightbox() {
    document.getElementById("lightbox").classList.remove("open");
  }
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeLightbox();
  });
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return DASHBOARD_HTML


@app.route("/api/stats")
def stats():
    users        = get_all_users()
    today        = datetime.now().strftime("%Y-%m-%d")
    attendance   = get_attendance(today)
    all_unknown  = get_unknown_faces(today)
    return jsonify({
        "total_registered": len(users),
        "present_today":    len(set(r[2] for r in attendance)),
        "unknown_today":    len(all_unknown),
        "attendance_logs":  len(attendance),
    })


@app.route("/api/users")
def users():
    rows = get_all_users()
    return jsonify([
        {"id": r[0], "name": r[1], "age": r[2], "mobile": r[3]}
        for r in rows
    ])


@app.route("/api/attendance")
def attendance():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = get_attendance(date)
    return jsonify([
        {"id": r[0], "user_id": r[1], "name": r[2],
         "confidence": round(r[3] * 100, 1), "timestamp": r[4]}
        for r in rows
    ])


@app.route("/api/unknown")
def unknown():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    rows = get_unknown_faces(date)
    return jsonify([
        {"id": r[0], "image_path": r[1], "timestamp": r[2]}
        for r in rows
    ])


@app.route("/api/delete_user/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/api/delete_unknown/<int:record_id>", methods=["DELETE"])
def delete_unknown(record_id):
    conn   = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Get image path before deleting so we can remove the file too
    cursor.execute("SELECT image_path FROM unknown_faces WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    if row:
        import os
        try:
            os.remove(row[0])
        except FileNotFoundError:
            pass
    cursor.execute("DELETE FROM unknown_faces WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})


@app.route("/unknown_faces/<path:filename>")
def unknown_image(filename):
    return send_from_directory("unknown_faces", filename)


if __name__ == "__main__":
    sync_unknown_faces()
    app.run(debug=True, port=5000)