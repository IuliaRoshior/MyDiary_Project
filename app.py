"""My Diary — dependency-free Python/SQLite application.

Run ``python app.py`` and visit http://127.0.0.1:5000 .
This is a single-user local development server, not a public multi-tenant service.
"""
from __future__ import annotations

import json
import mimetypes
import os
import sqlite3
from datetime import date, datetime, timedelta
from contextlib import closing
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
DATABASE = os.environ.get("MYDIARY_DB", str(BASE_DIR / "mydiary.sqlite3"))
PRIORITIES = {"low", "medium", "high"}
STATUSES = {"all", "active", "completed", "overdue"}
MAX_BODY = 16 * 1024


def iso_date(value):
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def validate_task(body, partial=False):
    if not isinstance(body, dict):
        return None, "A JSON object is required."
    allowed = {"title", "description", "due_date", "priority", "completed"}
    if not partial:
        if "title" not in body:
            return None, "Task title is required."
        if "due_date" not in body:
            return None, "Due date is required."
        body = {"description": "", "priority": "medium", "completed": False, **body}
    if not body:
        return None, "Provide a field to update."
    result = {}
    for key, value in body.items():
        if key not in allowed:
            return None, f"Unknown field: {key}."
        if key == "title":
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > 120:
                return None, "Title must be between 1 and 120 characters."
            result[key] = value.strip()
        elif key == "description":
            if not isinstance(value, str) or len(value) > 1000:
                return None, "Description must be at most 1000 characters."
            result[key] = value.strip()
        elif key == "due_date":
            day = iso_date(value)
            if day is None:
                return None, "Due date must be in YYYY-MM-DD format."
            result[key] = day
        elif key == "priority":
            if value not in PRIORITIES:
                return None, "Priority must be low, medium or high."
            result[key] = value
        elif key == "completed":
            if not isinstance(value, bool):
                return None, "Completed must be true or false."
            result[key] = int(value)
    return result, None


def connect(database=DATABASE):
    conn = sqlite3.connect(database, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=10000")
    return conn


def initialize(database=DATABASE, seed_demo=True):
    Path(database).parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(database)) as conn, conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                due_date TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'medium' CHECK(priority IN ('low','medium','high')),
                completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0,1)),
                completed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
            CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed);
        """)
        if seed_demo and conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
            seed(conn)


def seed(conn):
    today = date.today()
    samples = [
        ("Plan the week ahead", -3, "high", 1, -3, "Prioritize three meaningful goals."),
        ("Review design references", -2, "medium", 1, -2, "Collect inspiration and useful layouts."),
        ("Clear the inbox", -1, "low", 1, -1, "Archive and reply to important messages."),
        ("Morning journaling", 0, "low", 1, 0, "Write down one thing worth remembering."),
        ("Update portfolio case study", 0, "high", 0, None, "Refine typography and project storytelling."),
        ("Read for 20 minutes", 0, "low", 0, None, "Enjoy a little offline time."),
        ("Prepare project presentation", 0, "medium", 0, None, "Outline key screens and functionality."),
        ("Send the project proposal", 1, "high", 0, None, "Check links and attach the right files."),
        ("Organize Figma components", 2, "medium", 0, None, "Name layers and document variants."),
        ("Sketch new dashboard ideas", 3, "low", 0, None, "Explore layouts without constraints."),
        ("Check monthly goals", 5, "medium", 0, None, "Track progress and adjust priorities."),
        ("Final QA pass", -2, "high", 0, None, "Check responsiveness and interactions."),
        ("Collect feedback", -6, "medium", 1, -4, "Capture notes for the next iteration."),
        ("Publish updated designs", -7, "high", 1, -6, "Export presentation-ready previews."),
    ]
    now = datetime.now().isoformat(timespec="seconds")
    for title, offset, priority, completed, completion_offset, description in samples:
        due = (today + timedelta(days=offset)).isoformat()
        finished = (datetime.now() + timedelta(days=completion_offset)).isoformat(timespec="seconds") if completion_offset is not None else None
        conn.execute("""
            INSERT INTO tasks(title,description,due_date,priority,completed,completed_at,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (title, description, due, priority, completed, finished, now, now))


def as_task(row):
    return {"id": row["id"], "title": row["title"], "description": row["description"],
            "due_date": row["due_date"], "priority": row["priority"],
            "completed": bool(row["completed"]), "completed_at": row["completed_at"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "overdue": not row["completed"] and row["due_date"] < date.today().isoformat()}


def list_tasks(conn, query):
    day = query.get("date", [""])[0]
    if day and not iso_date(day):
        return {"error": "Invalid date. Use YYYY-MM-DD."}, 400
    status = query.get("status", ["all"])[0]
    if status not in STATUSES:
        return {"error": "Invalid task status."}, 400
    sql = "SELECT * FROM tasks WHERE 1=1"
    args = []
    if day:
        sql += " AND due_date=?"; args.append(day)
    if status == "active":
        sql += " AND completed=0"
    elif status == "completed":
        sql += " AND completed=1"
    elif status == "overdue":
        sql += " AND completed=0 AND due_date<?"; args.append(date.today().isoformat())
    search = query.get("q", [""])[0].strip()
    if search:
        sql += " AND (title LIKE ? OR description LIKE ?)"
        args.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY completed ASC, CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, due_date ASC, id DESC"
    return {"tasks": [as_task(row) for row in conn.execute(sql, args).fetchall()]}, 200


def add_task(conn, body):
    fields, error = validate_task(body)
    if error:
        return {"error": error}, 400
    now = datetime.now().isoformat(timespec="seconds")
    finished = now if fields["completed"] else None
    cur = conn.execute("""
        INSERT INTO tasks(title,description,due_date,priority,completed,completed_at,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (fields["title"], fields["description"], fields["due_date"], fields["priority"], fields["completed"], finished, now, now))
    conn.commit()
    return {"task": as_task(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())}, 201


def edit_task(conn, task_id, body):
    fields, error = validate_task(body, partial=True)
    if error:
        return {"error": error}, 400
    old = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if old is None:
        return {"error": "Task not found."}, 404
    now = datetime.now().isoformat(timespec="seconds")
    if "completed" in fields:
        fields["completed_at"] = (now if not old["completed"] else old["completed_at"]) if fields["completed"] else None
    fields["updated_at"] = now
    columns = ", ".join(f"{column}=?" for column in fields)
    conn.execute(f"UPDATE tasks SET {columns} WHERE id=?", (*fields.values(), task_id))
    conn.commit()
    return {"task": as_task(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())}, 200


def delete_task(conn, task_id):
    cur = conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    if cur.rowcount == 0:
        return {"error": "Task not found."}, 404
    conn.commit()
    return None, 204


def get_stats(conn):
    rows = conn.execute("SELECT due_date, completed, completed_at FROM tasks").fetchall()
    year = date.today().year
    completed = [r for r in rows if r["completed"]]
    active = [r for r in rows if not r["completed"]]
    on_time = [r for r in completed if r["completed_at"] and r["completed_at"][:10] <= r["due_date"]]
    late_done = [r for r in completed if r["completed_at"] and r["completed_at"][:10] > r["due_date"]]
    overdue = [r for r in active if r["due_date"] < date.today().isoformat()]
    current = [r for r in completed if r["completed_at"] and r["completed_at"][:4] == str(year)]
    previous = [r for r in completed if r["completed_at"] and r["completed_at"][:4] == str(year - 1)]
    late_current = [r for r in late_done if r["completed_at"][:4] == str(year)]
    late_previous = [r for r in late_done if r["completed_at"][:4] == str(year - 1)]
    def change(this, last):
        return round((this - last) / last * 100, 1) if last else None
    return {
        "total": len(rows), "completed": len(completed), "active": len(active),
        "on_time": len(on_time), "late_completed": len(late_done), "overdue": len(overdue),
        "completion_rate": round(len(completed)/len(rows)*100) if rows else 0,
        "on_time_rate": round(len(on_time)/len(completed)*100) if completed else 0,
        "overdue_rate": round(len(overdue)/len(active)*100) if active else 0,
        "completed_year": len(current), "completed_prev_year": len(previous),
        "late_year": len(late_current), "late_prev_year": len(late_previous),
        "completed_change": change(len(current), len(previous)),
        "late_change": change(len(late_current), len(late_previous)),
        "monthly_completed": [sum(1 for r in current if r["completed_at"][5:7] == f"{i:02d}") for i in range(1,13)],
        "year": year,
    }, 200


def get_calendar(conn, query):
    month = query.get("month", [""])[0]
    try:
        first = date.fromisoformat(month + "-01")
        if len(month) != 7 or month != f"{first.year:04d}-{first.month:02d}":
            raise ValueError
    except ValueError:
        return {"error": "Month must be YYYY-MM."}, 400
    nxt = date(first.year+1, 1, 1) if first.month == 12 else date(first.year, first.month+1, 1)
    rows = conn.execute("""
        SELECT due_date, COUNT(*) AS total, SUM(completed) AS completed
        FROM tasks WHERE due_date >= ? AND due_date < ? GROUP BY due_date
    """, (first.isoformat(), nxt.isoformat())).fetchall()
    return {"days": {r["due_date"]: {"total": r["total"], "completed": r["completed"]} for r in rows}}, 200


class DiaryServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, database=DATABASE, seed_demo=True):
        initialize(database, seed_demo=seed_demo)
        self.database = database
        super().__init__(address, DiaryHandler)


class DiaryHandler(BaseHTTPRequestHandler):
    server_version = "MyDiary/1.0"

    def log_message(self, format, *args):
        if not getattr(self.server, "quiet", False):
            super().log_message(format, *args)

    def send_json(self, data, status=200):
        payload = b"" if data is None else json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if payload:
            self.wfile.write(payload)

    def serve_file(self, path):
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            self.send_json({"error":"Not found."}, 404)
            return
        mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", mimetype + ("; charset=utf-8" if mimetype.startswith("text/") or mimetype in ("image/svg+xml", "application/javascript") else ""))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 1 or length > MAX_BODY:
            return None
        if "application/json" not in self.headers.get("Content-Type", ""):
            return None
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return None

    def route(self, method):
        parsed = urlparse(self.path)
        path = parsed.path
        if method == "GET":
            if path == "/":
                return self.serve_file(BASE_DIR / "templates" / "index.html")
            if path.startswith("/static/"):
                root = (BASE_DIR / "static").resolve()
                file = (root / path.removeprefix("/static/")).resolve()
                if file.is_relative_to(root) and file.is_file():
                    return self.serve_file(file)
                return self.send_json({"error": "Not found."}, 404)
            if path == "/api/health":
                return self.send_json({"status": "ok", "app": "My Diary"})
        with closing(connect(self.server.database)) as conn:
            query = parse_qs(parsed.query, keep_blank_values=True)
            if method == "GET" and path == "/api/tasks":
                data, status = list_tasks(conn, query)
            elif method == "GET" and path == "/api/stats":
                data, status = get_stats(conn)
            elif method == "GET" and path == "/api/calendar":
                data, status = get_calendar(conn, query)
            elif method == "POST" and path == "/api/tasks":
                data, status = add_task(conn, self.read_json())
            elif path.startswith("/api/tasks/") and path.split("/")[-1].isdigit():
                task_id = int(path.split("/")[-1])
                if method == "PATCH":
                    data, status = edit_task(conn, task_id, self.read_json())
                elif method == "DELETE":
                    data, status = delete_task(conn, task_id)
                else:
                    data, status = {"error":"Method not allowed."}, 405
            else:
                data, status = {"error":"Not found."}, 404
        self.send_json(data, status)

    def do_GET(self): self.route("GET")
    def do_POST(self): self.route("POST")
    def do_PATCH(self): self.route("PATCH")
    def do_DELETE(self): self.route("DELETE")


def serve(port=5000, host="127.0.0.1", database=DATABASE, seed_demo=True):
    httpd = DiaryServer((host, port), database, seed_demo=seed_demo)
    print(f"\n  My Diary is running at http://{host}:{httpd.server_address[1]}\n  Press Ctrl+C to stop.\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping My Diary…")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run My Diary locally")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "5000")))
    parser.add_argument("--empty", action="store_true", help="Disable demo data on first run")
    args = parser.parse_args()
    serve(port=args.port, seed_demo=not args.empty)
