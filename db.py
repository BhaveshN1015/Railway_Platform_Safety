"""
db.py — SQLite event store.

Tables
------
violations  : boundary-crossing events (entry/exit/dwell per track ID)
crowd_events: zone overcrowding events  (zone name, peak count, duration)
"""

import sqlite3
import threading
from datetime import datetime
from typing import Optional

import config

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS violations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id        INTEGER NOT NULL,
                camera_id       TEXT    NOT NULL DEFAULT 'cam-01',
                entry_ts        TEXT    NOT NULL,
                exit_ts         TEXT,
                dwell_sec       REAL,
                screenshot_path TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crowd_events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                zone_name   TEXT NOT NULL,
                camera_id   TEXT NOT NULL,
                event_ts    TEXT NOT NULL,
                peak_count  INTEGER NOT NULL,
                threshold   INTEGER NOT NULL,
                event_type  TEXT NOT NULL,
                screenshot_path TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v_entry ON violations(entry_ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_c_ts    ON crowd_events(event_ts)")
        conn.commit()
        conn.close()


# ── Boundary violations ─────────────────────────────────────

def log_entry(track_id: int, camera_id: str, screenshot_path: str) -> int:
    entry_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO violations (track_id, camera_id, entry_ts, screenshot_path) VALUES (?,?,?,?)",
            (track_id, camera_id, entry_ts, screenshot_path),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
    return row_id


def log_exit(row_id: int, entry_ts: str) -> None:
    exit_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        dwell = (datetime.strptime(exit_ts, fmt) - datetime.strptime(entry_ts, fmt)).total_seconds()
    except Exception:
        dwell = None
    with _lock:
        conn = _connect()
        conn.execute("UPDATE violations SET exit_ts=?, dwell_sec=? WHERE id=?", (exit_ts, dwell, row_id))
        conn.commit()
        conn.close()


# ── Crowd events ─────────────────────────────────────────────

def log_crowd_event(zone_name: str, camera_id: str, peak_count: int,
                    threshold: int, event_type: str, screenshot_path: str = "") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _lock:
        conn = _connect()
        conn.execute(
            """INSERT INTO crowd_events
               (zone_name, camera_id, event_ts, peak_count, threshold, event_type, screenshot_path)
               VALUES (?,?,?,?,?,?,?)""",
            (zone_name, camera_id, ts, peak_count, threshold, event_type, screenshot_path),
        )
        conn.commit()
        conn.close()


# ── Queries ──────────────────────────────────────────────────

def get_today_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM violations WHERE entry_ts LIKE ?", (f"{today}%",)
        ).fetchone()
        conn.close()
    return row["cnt"] if row else 0


def get_today_crowd_count() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM crowd_events WHERE event_ts LIKE ?", (f"{today}%",)
        ).fetchone()
        conn.close()
    return row["cnt"] if row else 0


def get_recent(n: int = 5) -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT track_id, camera_id, entry_ts, dwell_sec, screenshot_path "
            "FROM violations ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]


def get_recent_crowd(n: int = 5) -> list:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT zone_name, event_ts, peak_count, threshold, event_type "
            "FROM crowd_events ORDER BY id DESC LIMIT ?", (n,)
        ).fetchall()
        conn.close()
    return [dict(r) for r in rows]
