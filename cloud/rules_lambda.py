import json
from typing import Any, Dict

from common import (
    get_object_bytes, read_jsonl_bytes, put_object_bytes,
    run_rules_and_report, update_case_status,
    VERIFIED_BUCKET, REPORTS_BUCKET
)

def handler(event: Dict[str, Any], context):
    # S3 event on verified/*/minutes.jsonl
    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key    = rec["s3"]["object"]["key"]
        if bucket != VERIFIED_BUCKET or not key.endswith("/minutes.jsonl"):
            continue

        # verified/{case_id}/{ts}/minutes.jsonl
        _, case_id, ts_folder, _ = key.split("/", 3)

        minutes_blob = get_object_bytes(bucket, key)
        minutes = read_jsonl_bytes(minutes_blob)

        results, html = run_rules_and_report(minutes)

        # Store results + report
        res_key  = f"reports/{case_id}/{ts_folder}/results.json"
        html_key = f"reports/{case_id}/{ts_folder}/report.html"
        put_object_bytes(REPORTS_BUCKET, res_key, json.dumps(results).encode("utf-8"), "application/json")
        put_object_bytes(REPORTS_BUCKET, html_key, html, "text/html")

        # Update case status
        update_case_status(case_id, status="reported", last_report=html_key, last_ts=ts_folder)

    return {"statusCode": 200, "body": json.dumps({"ok": True})}
