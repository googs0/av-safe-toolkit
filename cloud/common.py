import os, io, json, gzip, datetime as dt, sqlite3, pathlib, urllib.parse
from typing import List, Dict, Any, Optional, Tuple

LOCAL_MODE = os.environ.get("LOCAL_MODE", "0") == "1"
BASE = pathlib.Path(os.environ.get("LOCAL_DATA_DIR", "./local_data")).resolve()

# Project imports 
from avsafe_descriptors.integrity.hash_chain import chain_hash, canonical_json
from avsafe_descriptors.integrity.signing import verify_bytes
from avsafe_descriptors.rules.profile_loader import load_profile
from avsafe_descriptors.rules.evaluator import evaluate_minutes
from avsafe_descriptors.report.render_html import render_report_html

# Env config
RAW_BUCKET      = os.environ.get("RAW_BUCKET", "avsafe-raw")
VERIFIED_BUCKET = os.environ.get("VERIFIED_BUCKET", "avsafe-verified")
REPORTS_BUCKET  = os.environ.get("REPORTS_BUCKET", "avsafe-reports")
TABLE_NAME      = os.environ.get("TABLE_NAME", "avsafe_cases")
DEVICES_TABLE   = os.environ.get("DEVICES_TABLE", "avsafe_devices")
PUBLIC_KEY_S3_URI = os.environ.get("PUBLIC_KEY_S3_URI", "")
PROFILE_KEY     = os.environ.get("PROFILE_KEY", "avsafe_descriptors/rules/profiles/who_ieee_profile.yaml")

# AWS clients (lazy import only if needed)
if not LOCAL_MODE:
    import boto3
    s3 = boto3.client("s3")
    ddb = boto3.resource("dynamodb")
    cases_tbl = ddb.Table(TABLE_NAME)
    devices_tbl = ddb.Table(DEVICES_TABLE) if DEVICES_TABLE else None
else:
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / RAW_BUCKET).mkdir(parents=True, exist_ok=True)
    (BASE / VERIFIED_BUCKET).mkdir(parents=True, exist_ok=True)
    (BASE / REPORTS_BUCKET).mkdir(parents=True, exist_ok=True)
    _db = sqlite3.connect(BASE / "cases.db")
    _db.execute("""create table if not exists cases(
        case_id text primary key,
        label text, owner_sub text, status text,
        last_ts text, last_verified_key text, last_report text,
        created_at text, updated_at text)""")
    _db.execute("""create table if not exists devices(
        device_id text primary key,
        public_key_pem text, updated_at text)""")
    _db.commit()

# Local path helpers
def _local_path(bucket: str, key: str) -> pathlib.Path:
    p = (BASE / bucket / key).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p

def _file_url(path: pathlib.Path) -> str:
    return "file://" + urllib.parse.quote(str(path))

# S3-like helpers
def presign_put(bucket: str, key: str, content_type="application/gzip",
                metadata: Optional[Dict[str, str]] = None, expires: int = 3600) -> str:
    if LOCAL_MODE:
        return _file_url(_local_path(bucket, key))
    return s3.generate_presigned_url("put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type, "Metadata": metadata or {}},
        ExpiresIn=expires)

def presign_get(bucket: str, key: str, expires: int = 3600) -> str:
    if LOCAL_MODE:
        return _file_url(_local_path(bucket, key))
    return s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires)

def get_object_bytes(bucket: str, key: str) -> bytes:
    if LOCAL_MODE:
        return _local_path(bucket, key).read_bytes()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()

def put_object_bytes(bucket: str, key: str, data: bytes, content_type="application/octet-stream"):
    if LOCAL_MODE:
        _local_path(bucket, key).write_bytes(data)
        return
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

# JSONL helpers
def jsonl_bytes(records: List[Dict[str, Any]]) -> bytes:
    buf = io.StringIO()
    for r in records:
        buf.write(json.dumps(r, ensure_ascii=False) + "\n")
    return buf.getvalue().encode("utf-8")

def read_jsonl_bytes(data: bytes) -> List[Dict[str, Any]]:
    try:
        if data[:2] == b"\x1f\x8b": data = gzip.decompress(data)
    except Exception: pass
    out: List[Dict[str, Any]] = []
    for line in data.splitlines():
        line = line.strip()
        if not line: continue
        out.append(json.loads(line))
    return out

# Device pubkeys
def _parse_s3_uri(uri: str) -> Tuple[str, str]:
    assert uri.startswith("s3://")
    b, k = uri[5:].split("/", 1)
    return b, k

def load_pubkey_map() -> Dict[str, str]:
    if not LOCAL_MODE:
        items: Dict[str, str] = {}
        if DEVICES_TABLE:
            resp = devices_tbl.scan(ProjectionExpression="device_id, public_key_pem")
            for it in resp.get("Items", []): items[it["device_id"]] = it["public_key_pem"]
            return items
        if PUBLIC_KEY_S3_URI:
            b, k = _parse_s3_uri(PUBLIC_KEY_S3_URI)
            blob = get_object_bytes(b, k)
            return json.loads(blob.decode("utf-8"))
        return {}
    # local sqlite
    cur = _db.execute("select device_id, public_key_pem from devices")
    return {device_id: pem for device_id, pem in cur.fetchall()}

# Case registry
def create_case(case_id: str, label: str, owner_sub: str = "unknown"):
    now = dt.datetime.utcnow().isoformat() + "Z"
    if not LOCAL_MODE:
        ddb.Table(TABLE_NAME).put_item(Item={
            "case_id": case_id, "label": label, "owner_sub": owner_sub,
            "status": "new", "created_at": now})
        return
    _db.execute("insert or replace into cases(case_id,label,owner_sub,status,created_at,updated_at) values(?,?,?,?,?,?)",
                (case_id, label, owner_sub, "new", now, now)); _db.commit()

def get_case(case_id: str) -> Optional[Dict[str, Any]]:
    if not LOCAL_MODE:
        return ddb.Table(TABLE_NAME).get_item(Key={"case_id": case_id}).get("Item")
    row = _db.execute("select case_id,label,owner_sub,status,last_ts,last_verified_key,last_report,created_at,updated_at from cases where case_id=?",
                      (case_id,)).fetchone()
    if not row: return None
    keys=["case_id","label","owner_sub","status","last_ts","last_verified_key","last_report","created_at","updated_at"]
    return dict(zip(keys,row))

def update_case_status(case_id: str, **kv):
    now = dt.datetime.utcnow().isoformat() + "Z"
    if not LOCAL_MODE:
        expr = "SET " + ", ".join(f"{k}=:{k}" for k in kv.keys())
        vals = {f":{k}": v for k,v in kv.items()}; vals[":u"]=now; expr += ", updated_at=:u"
        ddb.Table(TABLE_NAME).update_item(Key={"case_id": case_id}, UpdateExpression=expr, ExpressionAttributeValues=vals)
        return
    # local sqlite
    cols = ", ".join(f"{k}=?" for k in kv.keys())
    params = list(kv.values()) + [now, case_id]
    _db.execute(f"update cases set {cols}, updated_at=? where case_id=?", params); _db.commit()

# Verify chain + signatures
def verify_minutes_chain_and_signatures(minutes: List[Dict[str, Any]],
                                        pubkey_map: Dict[str, str]) -> Dict[str, Any]:
    prev_hash = None; device_id = None
    for i, rec in enumerate(minutes):
        payload = {k:v for k,v in rec.items() if k!="chain"}
        chain = rec.get("chain", {})
        device_id = payload.get("device_id", device_id)
        sig_status = None
        if device_id and device_id in pubkey_map:
            sig_status = verify_bytes(canonical_json(payload).encode("utf-8"), chain)
        computed = chain_hash(prev_hash, payload); chain_ok = (computed == chain.get("hash"))
        if not chain_ok or (sig_status is False) or (not chain.get("hash")):
            return {"ok":False,"break_index":i,"signature_ok":sig_status,"chain_ok":chain_ok,"device_id":device_id}
        prev_hash = chain["hash"]
    return {"ok":True,"last_hash":prev_hash,"count":len(minutes),"device_id":device_id}

# Rules + HTML
def run_rules_and_report(
    minutes: List[Dict[str, Any]],
    profile_key: Optional[str] = None,
) -> (Dict[str, Any], bytes):
    import tempfile, json, os

    profile = load_profile(profile_key or PROFILE_KEY)

    # Write minutes to a temp JSONL (file-based evaluator)
    fd_m, p_m = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd_m)
    with open(p_m, "w", encoding="utf-8") as fm:
        for m in minutes:
            fm.write(json.dumps(m, ensure_ascii=False) + "\n")

    # Evaluate using file path API
    results = evaluate(p_m, profile)

    # Write results JSON for renderer
    fd_r, p_r = tempfile.mkstemp(suffix=".json")
    os.close(fd_r)
    with open(p_r, "w", encoding="utf-8") as fr:
        json.dump(results, fr, ensure_ascii=False, indent=2)

    # Render HTML to a temp file, then return bytes
    fd_h, p_h = tempfile.mkstemp(suffix=".html")
    os.close(fd_h)
    render(p_m, results_path=p_r, out_html=p_h, footnote=None)

    html_bytes = open(p_h, "rb").read()
    return results, html_bytes
