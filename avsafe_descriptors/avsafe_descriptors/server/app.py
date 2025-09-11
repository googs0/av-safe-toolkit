
from __future__ import annotations
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse
import uuid, os, json, tempfile
from ..io import jsonl_io, sqlite_store
from ..rules.profile_loader import load_profile
from ..rules.evaluator import evaluate
from ..report.render_html import render

DB = os.environ.get("AVSAFE_DB", "avsafe.db")
sqlite_store.ensure_schema(DB)
app = FastAPI(title="AV-SAFE Receiver")

@app.post("/session")
def create_session(name: str = Form(...)):
    sid = f"{name}-{uuid.uuid4().hex[:8]}"
    return {"session_id": sid}

@app.post("/session/{session_id}/ingest_jsonl")
async def ingest_jsonl(session_id: str, file: UploadFile):
    content = (await file.read()).decode('utf-8')
    # parse and insert
    records = [json.loads(line) for line in content.splitlines() if line.strip()]
    rows = sqlite_store.ingest(DB, session_id, records)
    return {"ingested": rows}

@app.post("/session/{session_id}/evaluate")
async def run_evaluate(session_id: str, body: dict):
    rules_yaml = body.get("rules_yaml")
    locale = body.get("locale")
    if not rules_yaml:
        return JSONResponse({"error":"rules_yaml required"}, status_code=400)
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as tf:
        tf.write(rules_yaml)
        tf.flush()
        prof = load_profile(tf.name)
    # Build minutes from DB for this session
    # For simplicity, we dump a temp JSONL constructed from DB rows
    from sqlalchemy import create_engine, text
    eng = create_engine(f"sqlite:///{DB}")
    with eng.begin() as cx:
        rows = cx.execute(text("SELECT * FROM minutes WHERE session=:s ORDER BY idx"), {"s": session_id}).mappings().all()
    minutes_path = tempfile.mktemp(suffix=".jsonl")
    with open(minutes_path,"w",encoding="utf-8") as f:
        for r in rows:
            rec = {
                "idx": r["idx"], "ts": r["ts"],
                "audio": {"laeq_db": r["laeq"], "lcpeak_db": r["lcpeak"]},
                "light": {"tlm_freq_hz": r["tlm_freq_hz"], "tlm_mod_percent": r["tlm_mod_percent"], "flicker_index": r["flicker_index"]},
                "chain": {"hash": r["chain_hash"], "signature_hex": r["signature_hex"], "scheme": r["scheme"], "public_key_hex": r["public_key_hex"]}
            }
            f.write(json.dumps(rec)+"\n")
    res = evaluate(minutes_path, prof, locale=locale)
    return res

@app.get("/session/{session_id}/report", response_class=HTMLResponse)
def get_report(session_id: str):
    # Pull minutes and a basic default result (no locale/profile) for demo view
    from sqlalchemy import create_engine, text
    eng = create_engine(f"sqlite:///{DB}")
    with eng.begin() as cx:
        rows = cx.execute(text("SELECT * FROM minutes WHERE session=:s ORDER BY idx LIMIT 500"), {"s":session_id}).mappings().all()
    minutes_path = tempfile.mktemp(suffix=".jsonl")
    results_path = tempfile.mktemp(suffix=".json")
    with open(minutes_path,"w",encoding="utf-8") as f:
        for r in rows:
            rec = {
                "idx": r["idx"], "ts": r["ts"],
                "audio": {"laeq_db": r["laeq"], "lcpeak_db": r["lcpeak"]},
                "light": {"tlm_freq_hz": r["tlm_freq_hz"], "tlm_mod_percent": r["tlm_mod_percent"], "flicker_index": r["flicker_index"]},
                "chain": {"hash": r["chain_hash"], "signature_hex": r["signature_hex"], "scheme": r["scheme"], "public_key_hex": r["public_key_hex"]}
            }
            f.write(json.dumps(rec)+"\n")
    # Minimal faux result for display
    json.dump({"n_minutes": len(rows), "flags": [], "noise": {"limit_db": 55, "pct_over": 0, "mean_laeq": 0}, "flicker": {"evaluated": 0, "violations": 0, "pct_violations": 0}}, open(results_path,"w"))
    out_html = tempfile.mktemp(suffix=".html")
    render(minutes_path, results_path, out_html)
    return HTMLResponse(open(out_html,"r",encoding="utf-8").read())
