import os, time, json, datetime as dt
from typing import Optional
import boto3
from fastapi import FastAPI
from pydantic import BaseModel
from mangum import Mangum

RAW_BUCKET = os.environ["RAW_BUCKET"]

s3 = boto3.client("s3")
app = FastAPI(title="AV-SAFE Serverless API")

class IngestStart(BaseModel):
    case_id: str
    device_id: str
    filename: Optional[str] = None  # default minutes.jsonl.gz

@app.get("/health")
def health():
    return {"status": "ok", "time": dt.datetime.utcnow().isoformat() + "Z"}

@app.post("/ingest/start")
def ingest_start(body: IngestStart):
    ts = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    fname = body.filename or "minutes.jsonl.gz"
    key = f"raw/{body.case_id}/{ts}/{fname}"

    # Pre-signed PUT URL (device can PUT file directly)
    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": RAW_BUCKET, "Key": key, "ContentType": "application/gzip",
                "Metadata": {"device_id": body.device_id, "case_id": body.case_id}},
        ExpiresIn=3600
    )
    return {"upload_url": url, "s3_key": key, "bucket": RAW_BUCKET}

handler = Mangum(app)
