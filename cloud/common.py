import os, json, gzip, io, datetime as dt
import boto3

# Import existing integrity + rules utilities
from avsafe_descriptors.integrity.hash_chain import chain_hash, canonical_json
from avsafe_descriptors.integrity.signing import verify_bytes   # your verify
from avsafe_descriptors.rules.profile_loader import load_profile
from avsafe_descriptors.rules.evaluator import evaluate_minutes
from avsafe_descriptors.report.render_html import render_report_html

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

RAW_BUCKET        = os.environ.get("RAW_BUCKET")
VERIFIED_BUCKET   = os.environ.get("VERIFIED_BUCKET")
REPORTS_BUCKET    = os.environ.get("REPORTS_BUCKET")
TABLE_NAME        = os.environ.get("TABLE_NAME")
PUBLIC_KEY_S3_URI = os.environ.get("PUBLIC_KEY_S3_URI", "")  # e.g. s3://my-bucket/keys/device_pubkeys.json

def _parse_s3_uri(uri: str):
    assert uri.startswith("s3://")
    _, rest = uri.split("s3://", 1)
    b, k = rest.split("/", 1)
    return b, k

def load_pubkey_map() -> dict:
    """Load device_id → public_key (PEM or raw) map from S3 JSON."""
    if not PUBLIC_KEY_S3_URI:
        return {}
    b, k = _parse_s3_uri(PUBLIC_KEY_S3_URI)
    obj = s3.get_object(Bucket=b, Key=k)
    data = obj["Body"].read()
    return json.loads(data)

def get_object_bytes(bucket: str, key: str) -> bytes:
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj["Body"].read()

def put_object_bytes(bucket: str, key: str, data: bytes, content_type="application/octet-stream"):
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

def jsonl_bytes(records: list[dict]) -> bytes:
    out = io.StringIO()
    for r in records:
        out.write(json.dumps(r, ensure_ascii=False) + "\n")
    return out.getvalue().encode("utf-8")

def read_jsonl_bytes(data: bytes) -> list[dict]:
    # Transparently handle .gz
    try:
        if data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
    except Exception:
        pass
    lines = []
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
        lines.append(json.loads(line))
    return lines

def verify_minutes_chain_and_signatures(minutes: list[dict], pubkey_map: dict) -> dict:
    """
    Verify per-minute: (a) signature over canonical payload (without 'chain'),
    (b) hash-chain continuity via chain_hash(prev_hash, payload).
    Returns summary dict.
    """
    prev_hash = None
    ok = True
    break_index = None
    device_id = None

    for i, rec in enumerate(minutes):
        payload = {k: v for k, v in rec.items() if k != "chain"}
        chain = rec.get("chain", {})
        device_id = payload.get("device_id", device_id)

        # Signature check (device-specific pubkey)
        pub = pubkey_map.get(device_id or "", None)
        if pub:
            sig_ok = verify_bytes(canonical_json(payload).encode("utf-8"), chain)
        else:
            # If no key registered, mark as failed but continue to pinpoint index
            sig_ok = False

        # Chain check
        computed_hash = chain_hash(prev_hash, payload)
        chain_ok = (computed_hash == chain.get("hash"))

        if not (sig_ok and chain_ok and chain.get("hash")):
            ok = False
            break_index = i
            break

        prev_hash = chain["hash"]

    return {
        "ok": ok,
        "break_index": break_index,
        "last_hash": prev_hash,
        "device_id": device_id,
    }

def run_rules_and_report(minutes: list[dict], profile_key: str = "avsafe_descriptors/rules/profiles/who_ieee_profile.yaml") -> tuple[dict, bytes]:
    """
    Evaluate minutes against WHO/IEEE profile, produce JSON results and HTML report bytes.
    """
    profile = load_profile(profile_key)
    results = evaluate_minutes(minutes, profile)
    html = render_report_html(minutes, results, profile)
    return results, html
