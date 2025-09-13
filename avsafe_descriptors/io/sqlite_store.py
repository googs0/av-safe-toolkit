# avsafe_descriptors/io/sqlite_store.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Iterator, Literal, Mapping, Optional, Sequence, Union

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

PathLike = Union[str, Path]
ConflictMode = Literal["insert", "ignore", "replace"]
OnError = Literal["raise", "skip"]

__all__ = [
    "ensure_schema",
    "ingest",
    "list_sessions",
    "session_summary",
    "query_minutes",
    "delete_session",
    "open_engine",
]


def open_engine(db_path: PathLike) -> Engine:
    """
    Create a SQLAlchemy engine for an on-disk SQLite database.
    Uses WAL mode and pre-ping for resilience.
    """
    db_uri = f"sqlite:///{Path(db_path)}"
    eng = create_engine(db_uri, future=True, pool_pre_ping=True)
    # Set pragmatic defaults each time we connect
    with eng.begin() as cx:
        cx.execute(text("PRAGMA journal_mode=WAL"))
        cx.execute(text("PRAGMA synchronous=NORMAL"))
        cx.execute(text("PRAGMA foreign_keys=ON"))
    return eng


def ensure_schema(db_path: PathLike) -> None:
    """
    Create tables and indices if they do not exist.
    Tries SQLite STRICT tables when available; falls back otherwise.
    """
    eng = open_engine(db_path)
    with eng.begin() as cx:
        # Try STRICT table (SQLite >= 3.37). If it fails, create a non-STRICT table.
        try:
            cx.execute(text("""
                CREATE TABLE IF NOT EXISTS minutes (
                    session         TEXT    NOT NULL,
                    idx             INTEGER NOT NULL,
                    ts              TEXT    NOT NULL,
                    laeq            REAL,
                    lcpeak          REAL,
                    tlm_freq_hz     REAL,
                    tlm_mod_percent REAL,
                    flicker_index   REAL,
                    third_oct       TEXT,   -- JSON serialized string
                    chain_hash      TEXT    NOT NULL,
                    signature_hex   TEXT,
                    scheme          TEXT,
                    public_key_hex  TEXT,
                    PRIMARY KEY (session, idx)
                ) STRICT
            """))
        except Exception:
            cx.execute(text("""
                CREATE TABLE IF NOT EXISTS minutes (
                    session         TEXT    NOT NULL,
                    idx             INTEGER NOT NULL,
                    ts              TEXT    NOT NULL,
                    laeq            REAL,
                    lcpeak          REAL,
                    tlm_freq_hz     REAL,
                    tlm_mod_percent REAL,
                    flicker_index   REAL,
                    third_oct       TEXT,   -- JSON serialized string
                    chain_hash      TEXT    NOT NULL,
                    signature_hex   TEXT,
                    scheme          TEXT,
                    public_key_hex  TEXT,
                    PRIMARY KEY (session, idx)
                )
            """))
        # Helpful indices (PRIMARY KEY already covers session+idx)
        cx.execute(text("CREATE INDEX IF NOT EXISTS ix_minutes_session_ts ON minutes(session, ts)"))
        cx.execute(text("CREATE INDEX IF NOT EXISTS ix_minutes_session_chain ON minutes(session, chain_hash)"))


def _convert_record(session: str, r: Mapping) -> dict:
    """
    Convert one minute-summary record to DB row mapping.
    Validates presence of required fields; raises ValueError if missing.
    """
    try:
        audio = r.get("audio", {}) or {}
        light = r.get("light", {}) or {}
        chain = r.get("chain", {}) or {}
        return {
            "session": session,
            "idx": r["idx"],
            "ts": r["ts"],
            "laeq": audio.get("laeq_db"),
            "lcpeak": audio.get("lcpeak_db"),
            "tlm_freq_hz": light.get("tlm_freq_hz"),
            "tlm_mod_percent": light.get("tlm_mod_percent"),
            "flicker_index": light.get("flicker_index"),
            "third_oct": json.dumps(audio.get("third_octave_db", {}), ensure_ascii=False),
            "chain_hash": chain["hash"],
            "signature_hex": chain.get("signature_hex"),
            "scheme": chain.get("scheme"),
            "public_key_hex": chain.get("public_key_hex"),
        }
    except KeyError as e:
        raise ValueError(f"Record missing required key: {e!s}") from e


def ingest(
    db_path: PathLike,
    session: str,
    records: Iterable[Mapping],
    *,
    conflict: ConflictMode = "replace",
    on_error: OnError = "raise",
    chunk_size: int = 1000,
) -> int:
    """
    Ingest minute-summary records into SQLite.

    - conflict:
        - "insert": regular INSERT (error on duplicates)
        - "ignore": INSERT OR IGNORE (skip duplicates)
        - "replace": INSERT OR REPLACE (upsert)  [default]
    - on_error: "raise" or "skip" malformed records
    - chunk_size: batch size for executemany

    Returns number of rows written (for 'ignore', this is attempted rows; skipped duplicates are not counted by SQLite).
    """
    verb = {
        "insert": "INSERT",
        "ignore": "INSERT OR IGNORE",
        "replace": "INSERT OR REPLACE",
    }[conflict]

    stmt = text(f"""
        {verb} INTO minutes
        (session, idx, ts, laeq, lcpeak, tlm_freq_hz, tlm_mod_percent, flicker_index,
         third_oct, chain_hash, signature_hex, scheme, public_key_hex)
        VALUES
        (:session, :idx, :ts, :laeq, :lcpeak, :tlm_freq_hz, :tlm_mod_percent, :flicker_index,
         :third_oct, :chain_hash, :signature_hex, :scheme, :public_key_hex)
    """)

    eng = open_engine(db_path)
    total = 0
    batch: list[dict] = []

    def flush_batch(engine: Engine, items: list[dict]) -> int:
        if not items:
            return 0
        with engine.begin() as cx:
            cx.execute(stmt, items)  # executemany
        return len(items)

    for r in records:
        try:
            row = _convert_record(session, r)
        except ValueError:
            if on_error == "skip":
                continue
            raise
        batch.append(row)
        if len(batch) >= chunk_size:
            total += flush_batch(eng, batch)
            batch.clear()

    total += flush_batch(eng, batch)
    return total


# ------------------------
# Convenience query helpers
# ------------------------

def list_sessions(db_path: PathLike) -> list[str]:
    """Return distinct session IDs present in the DB (sorted)."""
    eng = open_engine(db_path)
    with eng.begin() as cx:
        rows = cx.execute(text("SELECT DISTINCT session FROM minutes ORDER BY session")).all()
    return [r[0] for r in rows]


def session_summary(db_path: PathLike, session: str) -> dict:
    """
    Return a small summary for a session:
    - count
    - idx_min / idx_max
    - ts_min / ts_max
    - laeq_avg / tlm_mod_avg (if present)
    """
    eng = open_engine(db_path)
    q = text("""
        SELECT
            COUNT(*)                         AS count,
            MIN(idx)                         AS idx_min,
            MAX(idx)                         AS idx_max,
            MIN(ts)                          AS ts_min,
            MAX(ts)                          AS ts_max,
            AVG(laeq)                        AS laeq_avg,
            AVG(tlm_mod_percent)             AS tlm_mod_avg
        FROM minutes
        WHERE session = :session
    """)
    with eng.begin() as cx:
        row = cx.execute(q, {"session": session}).mappings().first()
    return dict(row or {})


def query_minutes(
    db_path: PathLike,
    session: str,
    *,
    start_idx: Optional[int] = None,
    end_idx: Optional[int] = None,
    limit: Optional[int] = 1000,
) -> list[dict]:
    """
    Fetch minutes for a session, optionally bounded by idx and limited in count.
    Returns a list of dicts mirroring the table columns.
    """
    clauses = ["session = :session"]
    params: dict[str, object] = {"session": session}
    if start_idx is not None:
        clauses.append("idx >= :start_idx")
        params["start_idx"] = start_idx
    if end_idx is not None:
        clauses.append("idx <= :end_idx")
        params["end_idx"] = end_idx

    sql = f"""
        SELECT session, idx, ts, laeq, lcpeak, tlm_freq_hz, tlm_mod_percent, flicker_index,
               third_oct, chain_hash, signature_hex, scheme, public_key_hex
        FROM minutes
        WHERE {' AND '.join(clauses)}
        ORDER BY idx ASC
        {'' if limit is None else 'LIMIT :limit'}
    """.strip()
    if limit is not None:
        params["limit"] = int(limit)

    eng = open_engine(db_path)
    with eng.begin() as cx:
        rows = cx.execute(text(sql), params).mappings().all()

    # Convert third_oct back to dict for convenience
    out: list[dict] = []
    for r in rows:
        rec = dict(r)
        try:
            rec["third_oct"] = json.loads(rec.get("third_oct") or "{}")
        except Exception:
            rec["third_oct"] = {}
        out.append(rec)
    return out


def delete_session(db_path: PathLike, session: str) -> int:
    """Delete all rows for a session. Returns number of rows deleted."""
    eng = open_engine(db_path)
    with eng.begin() as cx:
        res = cx.execute(text("DELETE FROM minutes WHERE session = :session"), {"session": session})
    return res.rowcount or 0
