from __future__ import annotations
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import json

try:
    from nacl.signing import VerifyKey
    _HAS_NACL = True
except Exception:
    _HAS_NACL = False

from avsafe_descriptors.io.minute_summary import MinuteSummary
from avsafe_descriptors.integrity.integrity import canonical_json, sha256_hex
from avsafe_descriptors.rules.engine import evaluate_rules, MinuteLike
from avsafe_descriptors.server.store import init_db, create_session, insert_minutes, list_minutes, insert_results, list_results
from avsafe_descriptors.server.report_core import html_from

app = FastAPI(title="AV-SAFE Receiver (DB)", version="0.6.0")

@app.on_event("startup")
def _startup(): init_db()

class IngestEnvelope(BaseModel):
    minute: MinuteSummary
    expected_prev_hash: str | None = None
    public_key_hex: str | None = None

@app.get("/health")
def health(): return {"status": "ok"}

@app.post("/ingest/minute")
def ingest_minute(env: IngestEnvelope):
    m = env.minute
    payload = m.model_dump()
    if env.expected_prev_hash is not None and m.prev_hash != env.expected_prev_hash:
        raise HTTPException(status_code=400, detail="prev_hash mismatch")
    payload_no_sig = dict(payload); payload_no_sig.pop("signature", None)
    local_hash = sha256_hex(payload_no_sig)

    sig_ok = None
    if m.signature and env.public_key_hex and _HAS_NACL:
        try:
            vk = VerifyKey(bytes.fromhex(env.public_key_hex))
            vk.verify(canonical_json(payload_no_sig), bytes.fromhex(m.signature))
            sig_ok = True
        except Exception:
            sig_ok = False
    return {"accepted": True, "local_hash": local_hash, "prev_hash": m.prev_hash, "signature_verified": sig_ok}

@app.post("/session")
def new_session(name: str | None = Form(default=None)):
    sid = create_session(name=name); return {"session_id": sid, "name": name}

@app.post("/session/{session_id}/ingest_jsonl")
async def ingest_jsonl(session_id: str, file: UploadFile = File(...)):
    try:
        lines = (await file.read()).decode("utf-8").splitlines()
        rows = []
        for line in lines:
            if not line.strip(): continue
            j = json.loads(line); MinuteSummary.model_validate(j)
            payload_no_sig = dict(j); payload_no_sig.pop("signature", None)
            j.setdefault("local_hash", sha256_hex(payload_no_sig))
            rows.append(j)
        insert_minutes(session_id, rows)
        return {"accepted": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

class EvaluateRequest(BaseModel):
    rules_yaml: str

@app.post("/session/{session_id}/evaluate")
def evaluate(session_id: str, req: EvaluateRequest):
    minutes_json = list_minutes(session_id)
    minutes = []
    for j in minutes_json:
        ts = datetime.fromisoformat(j["timestamp_utc"].replace("Z","+00:00"))
        minutes.append(MinuteLike(timestamp_utc=ts, laeq_db=j.get("laeq_db"), lcpeak_db=j.get("lcpeak_db"),
                                  tlm_f_dom_hz=j.get("tlm_f_dom_hz"), tlm_percent_mod=j.get("tlm_percent_mod"),
                                  tlm_flicker_index=j.get("tlm_flicker_index")))
    results = evaluate_rules(minutes, req.rules_yaml)
    insert_results(session_id, [r.model_dump() for r in results])
    return {"n_results": len(results)}

@app.get("/session/{session_id}/report", response_class=HTMLResponse)
def report(session_id: str, public_key_hex: str | None = Query(default=None)):
    minutes_json = list_minutes(session_id); results_json = list_results(session_id)
    total_links = max(0, len(minutes_json)-1); ok_links = 0
    for i in range(1, len(minutes_json)):
        if minutes_json[i-1].get('local_hash') and minutes_json[i].get('prev_hash') == minutes_json[i-1].get('local_hash'): ok_links += 1
    chain_pct = (ok_links/total_links*100.0) if total_links>0 else 0.0

    sig_count, sig_ok = 0, 0
    if public_key_hex and _HAS_NACL:
        from nacl.signing import VerifyKey
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        for m in minutes_json:
            sig = m.get('signature')
            if sig:
                sig_count += 1
                payload_no_sig = dict(m); payload_no_sig.pop('signature', None)
                try:
                    vk.verify(canonical_json(payload_no_sig), bytes.fromhex(sig)); sig_ok += 1
                except Exception: pass
    elif public_key_hex and not _HAS_NACL:
        sig_count = sum(1 for m in minutes_json if m.get('signature'))

    integrity = {"minutes": len(minutes_json), "hash_chain_continuity_%": round(chain_pct, 2), "signed_minutes": sig_count, "signatures_verified": sig_ok if public_key_hex else "N/A"}
    html = html_from(minutes_json, results_json, integrity_summary=integrity); return HTMLResponse(content=html)
