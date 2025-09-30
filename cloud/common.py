import os, io, json, gzip, datetime as dt
from typing import List, Dict, Any, Optional, Tuple

import boto3

# Project imports (bundled)
from avsafe_descriptors.integrity.hash_chain import chain_hash, canonical_json
from avsafe_descriptors.integrity.signing import verify_bytes  # chain block with sig fields
from avsafe_descriptors.rules.profile_loader import load_profile
from avsafe_descriptors.rules.evaluator import evaluate_minutes
from avsafe_descriptors.report.render_html import render_report_html

# AWS clients
s3 = boto3.client("s3")
ddb = boto3.resource("dynamodb")

# Env config 
RAW_BUCKET      = os.environ["RAW_BUCKET"]
VERIFIED_BUCKET = os.environ["VERIFIED_BUCKET"]
REPORTS_BUCKET  = os.environ["REPORTS_BUCKET"]
TABLE_NAME      = os.environ["TABLE_NAME"]          # cases status/index
DEVICES_TABLE   = os.environ.get("DEVICES_TABLE")   # optional devices table (pubkeys)
PUBLIC_KEY_S3_URI = os.environ.get("PUBLIC_KEY_S3_URI", "")  # fallback: s3://bucket/path/pubkeys.json
PROFILE_KEY     = os.environ.get("PROFILE_KEY", "avsafe_descriptors/rules/profiles/who_ieee_profile.yaml")

cases_tbl   = ddb.Table(TABLE_NAME)
devices_tbl = ddb.Table(DEVICES_TABLE) if DEVICES_TABLE else None

# S3 helpers
def presign_put(bucket: str, key: str, content_type="application/gzip",
                metadata: Optional[Dict[str, str]] = None, expires: int = 3600) -> str:
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type, "Metadata": metadata or {}},
        ExpiresIn=expires
    )

def presign_get(bucket: str, key: str, expires: int = 3600) -> str:
    return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)

def get_object_bytes(bucket: str, key: str) -> bytes:
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()

def put_object_bytes(bucket: str, key: str, data: bytes, content_type="application/octet-stream"):
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

# JSONL helpers
def jsonl_bytes(records: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    for r in records:
        buf.write(json.dumps(r, ensure_ascii=False) + "\n")
    return buf.getvalue().encode("utf-8")

def read_jsonl_bytes(data: bytes) -> List[Dict[str, Any]]:
    # transparent .gz
    try:
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
    except Exception:
        pass
    out: List[Dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out

# Device pubkeys
def _parse_s3_uri(uri: str) -> Tuple[str, str]:
    assert uri.startswith("s3://")
    b, k = uri[5:].split("/", 1)
    return b, k

def load_pubkey_map() -> Dict[str, str]:
    """
    Device public keys for signature verification.
    Priority: DynamoDB DEVICES_TABLE (if set) else PUBLIC_KEY_S3_URI JSON map else {}.
    """
    if devices_tbl:
        items: Dict[str, str] = {}
        resp = devices_tbl.scan(ProjectionExpression="device_id, public_key_pem")
        for it in resp.get("Items", []):
            items[it["device_id"]] = it["public_key_pem"]
        return items
    if PUBLIC_KEY_S3_URI:
        b, k = _parse_s3_uri(PUBLIC_KEY_S3_URI)
        blob = get_object_bytes(b, k)
        return json.loads(blob.decode("utf-8"))
    return {}

# Case registry
def create_case(case_id: str, label: str, owner_sub: str = "unknown"):
    cases_tbl.put_item(Item={
        "case_id": case_id,
        "label": label,
        "owner_sub": owner_sub,
        "status": "new",
        "created_at": dt.datetime.utcnow().isoformat() + "Z",
    })

def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    return cases_tbl.get_item(Key={"case_id": case_id}).get("Item")

def update_case_status(case_id: str, **kv):
    expr = "SET " + ", ".join(f"{k}=:{k}" for k in kv.keys())
    vals = {f":{k}": v for k, v in kv.items()}
    vals[":u"] = dt.datetime.utcnow().isoformat() + "Z"
    expr += ", updated_at=:u"
    cases_tbl.update_item(Key={"case_id": case_id}, UpdateExpression=expr, ExpressionAttributeValues=vals)

# Verify chain + signatures
def verify_minutes_chain_and_signatures(minutes: List[Dict[str, Any]],
                                        pubkey_map: Dict[str, str]) -> Dict[str, Any]:
    """
    Verify per-minute (a) Ed25519 signature over canonical payload (if pubkey available),
    (b) hash-chain continuity via chain_hash(prev_hash, payload).
    Returns a summary with break index if any failure.
    """
    prev_hash = None
    device_id = None
    for i, rec in enumerate(minutes):
        payload = {k: v for k, v in rec.items() if k != "chain"}
        chain = rec.get("chain", {})
        device_id = payload.get("device_id", device_id)

        sig_status: Optional[bool] = None
        if device_id and device_id in pubkey_map:
            sig_status = verify_bytes(canonical_json(payload).encode("utf-8"), chain)

        computed = chain_hash(prev_hash, payload)
        chain_ok = (computed == chain.get("hash"))

        # Require chain_ok; signature may be None (no key) in dev,
        # but if present it must be True.
        if not chain_ok or (sig_status is False) or (not chain.get("hash")):
            return {
                "ok": False,
                "break_index": i,
                "signature_ok": sig_status,
                "chain_ok": chain_ok,
                "device_id": device_id,
            }
        prev_hash = chain["hash"]

    return {"ok": True, "last_hash": prev_hash, "count": len(minutes), "device_id": device_id}

# Rules + HTML
def run_rules_and_report(minutes: List[Dict[str, Any]], profile_key: Optional[str] = None) -> (Dict[str, Any], bytes):
    profile = load_profile(profile_key or PROFILE_KEY)
    results = evaluate_minutes(minutes, profile)
    html = render_report_html(minutes, results, profile)
    return results, (html if isinstance(html, (bytes, bytearray)) else html.encode("utf-8"))
