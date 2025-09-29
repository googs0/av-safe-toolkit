import os, json, datetime as dt
import boto3
from common import (
    get_object_bytes, read_jsonl_bytes, put_object_bytes,
    run_rules_and_report, VERIFIED_BUCKET, REPORTS_BUCKET, TABLE_NAME
)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key = rec["s3"]["object"]["key"]
        if not key.endswith("/minutes.jsonl"):
            continue
        # verified/{case_id}/{ts}/minutes.jsonl
        _, case_id, ts_folder, _ = key.split("/", 3)

        minutes_blob = get_object_bytes(bucket, key)
        minutes = read_jsonl_bytes(minutes_blob)

        results, html = run_rules_and_report(minutes)

        # Store results + HTML
        res_key = f"reports/{case_id}/{ts_folder}/results.json"
        html_key = f"reports/{case_id}/{ts_folder}/report.html"
        put_object_bytes(REPORTS_BUCKET, res_key, json.dumps(results).encode("utf-8"), "application/json")
        put_object_bytes(REPORTS_BUCKET, html_key, html if isinstance(html, bytes) else html.encode("utf-8"),
                         "text/html")

        # Update index
        table.update_item(
            Key={"case_id": case_id},
            UpdateExpression="SET last_report=:r, status=:s, updated_at=:u",
            ExpressionAttributeValues={
                ":r": html_key,
                ":s": "reported",
                ":u": dt.datetime.utcnow().isoformat() + "Z"
            }
        )
