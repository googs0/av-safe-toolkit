import json
from typing import Any, Dict
from cloud.common import (
    get_object_bytes, put_object_bytes, read_jsonl_bytes,
    load_pubkey_map, verify_minutes_chain_and_signatures,
    jsonl_bytes, update_case_status,
    RAW_BUCKET, VERIFIED_BUCKET
)

def handler(event: Dict[str, Any], context):
    # S3 event in cloud; in LOCAL_MODE call via local_runner instead.
    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key    = rec["s3"]["object"]["key"]
        if bucket != RAW_BUCKET or not key.startswith("raw/"): continue

        # raw/{case_id}/{ts}/minutes.jsonl.gz
        _, case_id, ts_folder, _ = key.split("/", 3)
        blob = get_object_bytes(bucket, key)
        minutes = read_jsonl_bytes(blob)

        pubkeys = load_pubkey_map()
        ver = verify_minutes_chain_and_signatures(minutes, pubkeys)

        ver_key = f"verified/{case_id}/{ts_folder}/verification.json"
        put_object_bytes(VERIFIED_BUCKET, ver_key, json.dumps(ver).encode("utf-8"), "application/json")

        min_key = f"verified/{case_id}/{ts_folder}/minutes.jsonl"
        put_object_bytes(VERIFIED_BUCKET, min_key, jsonl_bytes(minutes), "application/jsonl")

        status = "verified_ok" if ver.get("ok") else f"break_at_{ver.get('break_index')}"
        update_case_status(case_id, status=status, last_ts=ts_folder, last_verified_key=min_key)

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
