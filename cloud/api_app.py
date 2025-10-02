import uuid, datetime as dt
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from mangum import Mangum

from cloud import auth
from cloud.common import (
    RAW_BUCKET, REPORTS_BUCKET,
    presign_put, presign_get,
    create_case, get_case,
    update_case_status,
)

# No OpenAPI/docs
app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, title="AV-SAFE API")

class CaseCreate(BaseModel):
    label: str

class IngestStart(BaseModel):
    case_id: str
    device_id: str
    filename: Optional[str] = None

def _require(request: Request):
    try:
        return auth.require(dict(request.headers))
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@app.get("/health")
def health():
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat() + "Z"}

@app.post("/cases", status_code=201)
async def create_case_ep(body: CaseCreate, request: Request):
    claims = _require(request)
    case_id = uuid.uuid4().hex[:12].upper()
    create_case(case_id, body.label, owner_sub=claims.get("sub","unknown"))
    return {"case_id": case_id}

@app.get("/cases/{case_id}")
async def case_status_ep(case_id: str, request: Request):
    _require(request)
    item = get_case(case_id)
    if not item: raise HTTPException(404, "case not found")
    return item

@app.post("/ingest/start")
async def ingest_start_ep(body: IngestStart, request: Request):
    _require(request)
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = body.filename or "minutes.jsonl.gz"
    key = f"raw/{body.case_id}/{ts}/{fname}"
    url = presign_put(RAW_BUCKET, key, content_type="application/gzip",
                      metadata={"case_id": body.case_id, "device_id": body.device_id})
    update_case_status(body.case_id, status="ingesting", last_ts=ts)
    return {"upload_url": url, "bucket": RAW_BUCKET, "key": key, "ts": ts}

@app.get("/cases/{case_id}/reports/{ts}")
async def get_report_ep(case_id: str, ts: str, request: Request):
    _require(request)
    key = f"reports/{case_id}/{ts}/report.html"
    url = presign_get(REPORTS_BUCKET, key, expires=3600)
    return {"url": url}

handler = Mangum(app)
