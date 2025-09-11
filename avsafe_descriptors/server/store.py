from __future__ import annotations
import sqlite3, json, os, uuid

DEFAULT_DB = os.environ.get("AVSAFE_DB", "avsafe.db")

SCHEMA = [
    "PRAGMA foreign_keys=ON;",
    "CREATE TABLE IF NOT EXISTS sessions (session_id TEXT PRIMARY KEY, name TEXT, created_at TEXT DEFAULT (datetime('now')));",
    "CREATE TABLE IF NOT EXISTS minutes (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT REFERENCES sessions(session_id) ON DELETE CASCADE, timestamp_utc TEXT, payload_json TEXT, local_hash TEXT);",
    "CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, rule_id TEXT, severity TEXT, message TEXT, details_json TEXT, created_at TEXT DEFAULT (datetime('now')));",
    "CREATE INDEX IF NOT EXISTS idx_minutes_session ON minutes(session_id, timestamp_utc);",
    "CREATE INDEX IF NOT EXISTS idx_results_session ON results(session_id);"
]

def get_conn(db_path: str = DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn

def init_db(db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    for stmt in SCHEMA: cur.execute(stmt)
    conn.commit(); conn.close()

def create_session(name: str | None = None, db_path: str = DEFAULT_DB) -> str:
    sid = str(uuid.uuid4())
    conn = get_conn(db_path); conn.execute("INSERT INTO sessions(session_id, name) VALUES (?,?)", (sid, name))
    conn.commit(); conn.close(); return sid

def insert_minutes(session_id: str, rows, db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    for r in rows:
        cur.execute("INSERT INTO minutes(session_id, timestamp_utc, payload_json, local_hash) VALUES (?,?,?,?)",
                    (session_id, r.get("timestamp_utc"), json.dumps(r), r.get("local_hash","")))
    conn.commit(); conn.close()

def list_minutes(session_id: str, db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    cur.execute("SELECT payload_json FROM minutes WHERE session_id=? ORDER BY timestamp_utc ASC", (session_id,))
    rows = [json.loads(j) for (j,) in cur.fetchall()]; conn.close(); return rows

def insert_results(session_id: str, results, db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    for r in results:
        cur.execute("INSERT INTO results(session_id, rule_id, severity, message, details_json) VALUES (?,?,?,?,?)",
                    (session_id, r.get("rule_id"), r.get("severity"), r.get("message"), json.dumps(r.get("details", {}))))
    conn.commit(); conn.close()

def list_results(session_id: str, db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    cur.execute("SELECT rule_id, severity, message, details_json FROM results WHERE session_id=? ORDER BY id ASC", (session_id,))
    out = [{"rule_id":rid,"severity":sev,"message":msg,"details":json.loads(d or "{}")} for (rid,sev,msg,d) in cur.fetchall()]
    conn.close(); return out
