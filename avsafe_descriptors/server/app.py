# avsafe_descriptors/server/app.py
from __future__ import annotations

import json
import os
import tempfile
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, UploadFile, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from sqlalchemy import create_engine, text

from ..io import sqlite_store  # uses ensure_schema(...) and ingest(...)
from ..rules.profile_loader import load_profile
from ..rules.evaluator import evaluate
from ..report.render_html import render

# ---------------------------------------------------------------------------
# Config & startup
# ---------------------------------------------------------------------------

DB = os.environ.get("AVSAFE_DB", "avsafe.db")
sqlite_store.ensure_schema(DB)

app = FastAPI(
    title="AV-SAFE Receiver",
    description="Ingest privacy-preserving AV minute summaries, evaluate against WHO/IEEE-aligned rules, render tamper-evident reports.",
    version="1.0.0",
)

# Simple in-memory cache for idempotency (survives per-process; fine for dev/demo)
_IDEMP_CACHE: dict[tuple[str, str], dict] = {}
# (Optional) record of last upload stats per session for report convenience
_SESSION_LAST_RESULTS: dict[str, dict] = defaultdict(dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Dict[str, Any], status: int = 200) -> JSONResponse:
    return JSONResponse(data, status_code=status)


def _err(code: str, message: str, status: int = 400, details: Optional[Dict[str, Any]] = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": details or {}}}, status_code=status)


def _parse_jsonl_bytes(raw: bytes) -> List[dict]:
    """Parse newline-delimited JSON, skipping blank lines and raising on malformed rows."""
    out: List[dict] = []
    for i, line in enumerate(raw.decode("utf-8", errors="strict").splitlines()):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            out.append(obj)
        except Exception as e:
            raise ValueError(f"Malformed JSONL at line {i+1}: {e}") from e
    return out


def _basic_minute_check(m: dict) -> Optional[str]:
    """Lightweight schema sanity check (JSONL ingest). Return error string or None."""
    required_top = ["idx", "ts", "audio", "light", "chain"]
    for k in required_top:
        if k not in m:
            return f"missing field '{k}'"
    if "hash" not in m["chain"]:
        return "missing field 'chain.hash'"
    a = m["audio"]
    if not all(k in a for k in ("laeq_db", "lcpeak_db", "third_octave_db")):
        return "audio must include laeq_db, lcpeak_db, third_octave_db"
    l = m["light"]
    if not all(k in l for k in ("tlm_freq_hz", "tlm_mod_percent", "flicker_index")):
        return "light must include tlm_freq_hz, tlm_mod_percent, flicker_index"
    return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/session")
def create_session(name: Optional[str] = None):
    """
    Create a new ingestion/evaluation session.
    Request body may be empty or include {"name": "..."}; name is used as a friendly prefix.
    """
    prefix = (name or "session").strip().replace(" ", "_")
    sid = f"{prefix}-{uuid.uuid4().hex[:8]}"
    return {"session_id": sid, "expires_at": None}


@app.post("/session/{session_id}/ingest_jsonl")
async def ingest_jsonl(
    session_id: str,
    file: UploadFile,
    request: Request,
    idempotency_key: Optional[str] = Header(None, convert_underscores=False, alias="Idempotency-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Ingest newline-delimited JSON minute summaries for a session.
    - Honors optional Idempotency-Key header to avoid duplicate inserts.
    - Performs lightweight schema sanity checks (fast fail).
    """
    # Idempotency
    if idempotency_key:
        cache_key = (session_id, idempotency_key)
        if cache_key in _IDEMP_CACHE:
            # Return the previous receipt verbatim
            return _ok(_IDEMP_CACHE[cache_key], status=200)

    # Read upload
    raw = await file.read()
    try:
        records = _parse_jsonl_bytes(raw)
    except ValueError as e:
        return _err("bad_request", f"{e}", status=400)

    # Quick validation & stats
    accepted: List[dict] = []
    rejected = 0
    for m in records:
        reason = _basic_minute_check(m)
        if reason:
            rejected += 1
            continue
        accepted.append(m)

    # Store accepted minutes
    rows = 0
    if accepted:
        rows = sqlite_store.ingest(DB, session_id, accepted)

    receipt = {
        "session_id": session_id,
        "accepted_records": rows,
        "rejected_records": rejected,
        "checks": {
            "schema": "ok" if rejected == 0 else "partial",
            "chain_hash": "unchecked",   # deeper verification lives in evaluator/server-side pipeline
            "signatures": "present" if any(m.get("chain", {}).get("signature_hex") for m in accepted) else "missing",
        },
    }

    # Cache by idempotency key if present
    if idempotency_key:
        _IDEMP_CACHE[(session_id, idempotency_key)] = receipt

    # Save last ingest stats for the report page convenience
    _SESSION_LAST_RESULTS[session_id]["last_ingest"] = receipt
    return _ok(receipt, status=202)


@app.post("/session/{session_id}/evaluate")
async def run_evaluate(
    session_id: str,
    body: Dict[str, Any],
    idempotency_key: Optional[str] = Header(None, convert_underscores=False, alias="Idempotency-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
):
    """
    Evaluate previously ingested minutes for a session against an inline rules YAML.
    Body: { "rules_yaml": "...", "locale": "munich|..." }
    """
    rules_yaml = body.get("rules_yaml")
    locale = body.get("locale")
    if not rules_yaml or not isinstance(rules_yaml, str):
        return _err("bad_request", "rules_yaml required (string)", status=400)

    # Load profile from inline YAML (tempfile)
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as tf:
        tf.write(rules_yaml)
        tf.flush()
        prof = load_profile(tf.name)

    # Fetch minutes for this session in index order
    eng = create_engine(f"sqlite:///{DB}")
    with eng.begin() as cx:
        rows = cx.execute(
            text("SELECT * FROM minutes WHERE session=:s ORDER BY idx"),
            {"s": session_id},
        ).mappings().all()

    if not rows:
        return _err("unprocessable", "No minutes ingested for this session.", status=422)

    minutes_path = tempfile.mktemp(suffix=".jsonl")
    with open(minutes_path, "w", encoding="utf-8") as f:
        for r in rows:
            rec = {
                "idx": r["idx"],
                "ts": r["ts"],
                "audio": {"laeq_db": r["laeq"], "lcpeak_db": r["lcpeak"], "third_octave_db": json.loads(r["third_oct"]) if r["third_oct"] else {}},
                "light": {"tlm_freq_hz": r["tlm_freq_hz"], "tlm_mod_percent": r["tlm_mod_percent"], "flicker_index": r["flicker_index"]},
                "chain": {
                    "hash": r["chain_hash"],
                    "signature_hex": r["signature_hex"],
                    "scheme": r["scheme"],
                    "public_key_hex": r["public_key_hex"],
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Evaluate
    res = evaluate(minutes_path, prof, locale=locale)
    # Keep a pointer for the report page convenience
    _SESSION_LAST_RESULTS[session_id]["last_results"] = res

    return _ok(res, status=200)


@app.get("/session/{session_id}/report", response_class=HTMLResponse)
def get_report(
    session_id: str,
    public_key_hex: Optional[str] = None,
):
    """
    Render a human-readable HTML report.
    If results from /evaluate are cached, reuse them; otherwise produce a neutral placeholder.
    """
    # Pull minutes (cap rows for faster render)
    eng = create_engine(f"sqlite:///{DB}")
    with eng.begin() as cx:
        rows = cx.execute(
            text("SELECT * FROM minutes WHERE session=:s ORDER BY idx LIMIT 2000"),
            {"s": session_id},
        ).mappings().all()

    minutes_path = tempfile.mktemp(suffix=".jsonl")
    with open(minutes_path, "w", encoding="utf-8") as f:
        for r in rows:
            rec = {
                "idx": r["idx"],
                "ts": r["ts"],
                "audio": {"laeq_db": r["laeq"], "lcpeak_db": r["lcpeak"], "third_octave_db": json.loads(r["third_oct"]) if r["third_oct"] else {}},
                "light": {"tlm_freq_hz": r["tlm_freq_hz"], "tlm_mod_percent": r["tlm_mod_percent"], "flicker_index": r["flicker_index"]},
                "chain": {
                    "hash": r["chain_hash"],
                    "signature_hex": r["signature_hex"],
                    "scheme": r["scheme"],
                    "public_key_hex": r["public_key_hex"],
                },
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Use last evaluation if available; otherwise a minimal placeholder
    results_obj = _SESSION_LAST_RESULTS.get(session_id, {}).get("last_results") or {
        "n_minutes": len(rows),
        "flags": [],
        "noise": {"limit_db": None, "pct_over": 0, "mean_laeq": 0, "percentiles": None},
        "flicker": {"evaluated": 0, "violations": 0, "pct_violations": 0, "notes": "No evaluation run yet."},
        "trace": {"profile_id": None, "rules_version": "v1.0.0"},
    }

    # Render HTML
    out_html = tempfile.mktemp(suffix=".html")
    foot = None
    if public_key_hex:
        foot = f"Verification hint: client provided public key {public_key_hex[:16]}… (server-side signature checks appear in Integrity section)."

    render(minutes_path, results_path=_dump_json_temp(results_obj), out_html=out_html, footnote=foot)
    return HTMLResponse(open(out_html, "r", encoding="utf-8").read())


# ---------------------------------------------------------------------------
# Small utility to create a temp JSON file for renderer
# ---------------------------------------------------------------------------

def _dump_json_temp(obj: Dict[str, Any]) -> str:
    path = tempfile.mktemp(suffix=".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path
