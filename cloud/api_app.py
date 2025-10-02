# cloud/api_app.py
import uuid, datetime as dt
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from mangum import Mangum

app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, title="AV-SAFE API")

# ---------- models ----------
class CaseCreate(BaseModel):
    label: str

class IngestStart(BaseModel):
    case_id: str
    device_id: str
    filename: Optional[str] = None

# ---------- lazy service import ----------
def _svc():
    """
    Lazy-import backend pieces so Uvicorn can start even if a dependency is broken.
    Raises the original exception on first use for transparent debugging.
    """
    try:
        # package-qualified imports so CI resolves correctly
        from cloud import auth
        from cloud.common import (
            RAW_BUCKET, REPORTS_BUCKET,
            presign_put, presign_get,
            create_case, get_case, update_case_status,
        )
        return {
            "auth": auth,
            "RAW_BUCKET": RAW_BUCKET,
            "REPORTS_BUCKET": REPORTS_BUCKET,
            "presign_put": presign_put,
            "presign_get": presign_get,
            "create_case": create_case,
            "get_case": get_case,
            "update_case_status": update_case_status,
        }
    except Exception as e:
        # Surface the original import error later via HTTP 500
        raise e

def _require(request: Request):
    try:
        svc = _svc()
        return svc["auth"].require(dict(request.headers))
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth/Import error: {e}")

# ---------- routes ----------
@app.get("/health")
def health():
    # keep this route 100% import-free so the server can prove it's up
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat() + "Z"}

@app.post("/cases", status_code=201)
async def create_case_ep(body: CaseCreate, request: Request):
    _require(request)
    try:
        svc = _svc()
        case_id = uuid.uuid4().hex[:12].upper()
        svc["create_case"](case_id, body.label, owner_sub="unknown")  # will be set by auth in real use
        return {"case_id": case_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/cases error: {e}")

@app.get("/cases/{case_id}")
async def case_status_ep(case_id: str, request: Request):
    _require(request)
    try:
        svc = _svc()
        item = svc["get_case"](case_id)
        if not item:
            raise HTTPException(status_code=404, detail="case not found")
        return item
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/cases/{case_id} error: {e}")

@app.post("/ingest/start")
async def ingest_start_ep(body: IngestStart, request: Request):
    _require(request)
    try:
        svc = _svc()
        ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        fname = body.filename or "minutes.jsonl.gz"
        key = f"raw/{body.case_id}/{ts}/{fname}"
        url = svc["presign_put"](
            svc["RAW_BUCKET"], key,
            content_type="application/gzip",
            metadata={"case_id": body.case_id, "device_id": body.device_id},
        )
        svc["update_case_status"](body.case_id, status="ingesting", last_ts=ts)
        return {"upload_url": url, "bucket": svc["RAW_BUCKET"], "key": key, "ts": ts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/ingest/start error: {e}")

@app.get("/cases/{case_id}/reports/{ts}")
async def get_report_ep(case_id: str, ts: str, request: Request):
    _require(request)
    try:
        svc = _svc()
        key = f"reports/{case_id}/{ts}/report.html"
        url = svc["presign_get"](svc["REPORTS_BUCKET"], key, expires=3600)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"/reports error: {e}")

# AWS Lambda handler (safe even if imports are lazy)
handler = Mangum(app)
