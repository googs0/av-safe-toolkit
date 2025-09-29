import os, json, datetime as dt
import boto3
from common import (
    get_object_bytes, put_object_bytes, read_jsonl_bytes,
    verify_minutes_chain_and_signatures, load_pubkey_map,
    RAW_BUCKET, VERIFIED_BUCKET, TABLE_NAME
)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(TABLE_NAME)

def handler(event, context):
    # S3 event
    for rec in event.get("Records", []):
        bucket = rec["s3"]["bucket"]["name"]
        key = rec["s3"]["object"]["key"]
        if not key.startswith("raw/"):
            continue

        blob = get_object_bytes(bucket, key)
        minutes = read_jsonl_bytes(blob)

        pubkeys = load_pubkey_map()
        ver = verify_minutes_chain_and_signatures(minutes, pubkeys)

        # Write verification result JSON
        case_id = key.split("/")[1]
        ts_folder = key.split("/")[2]
        ver_key = f"verified/{case_id}/{ts_folder}/verification.json"
        put_object_bytes(VERIFIED_BUCKET, ver_key, json.dumps(ver).encode("utf-8"), "application/json")

        # (Optional) write minutes copy to verified/
        min_key = f"verified/{case_id}/{ts_folder}/minutes.jsonl"
        put_object_bytes(VERIFIED_BUCKET, min_key, b"".join([ (json.dumps(m)+"\n").encode() for m in minutes ]),
                         "application/jsonl")

        # Update DynamoDB index/status
        table.update_item(
            Key={"case_id": case_id},
            UpdateExpression="SET last_ts=:t, last_key=:k, status=:s, updated_at=:u",
            ExpressionAttributeValues={
                ":t": ts_folder,
                ":k": min_key,
                ":s": "verified_ok" if ver["ok"] else f"break_at_{ver['break_index']}",
                ":u": dt.datetime.utcnow().isoformat() + "Z"
            }
        )
