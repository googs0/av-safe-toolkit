#!/usr/bin/env python3
"""
Manage device public keys for AV-SAFE.

LOCAL_MODE=1 → uses SQLite at ./local_data/cases.db (table 'devices': device_id, public_key_pem)
Cloud mode   → prefers DynamoDB (DEVICES_TABLE), else S3 JSON at PUBLIC_KEY_S3_URI (s3://bucket/key)

Commands:
  enroll  --device DEV --pubkey pub.pem
  rotate  --device DEV --pubkey pub_new.pem
  revoke  --device DEV
  list

Examples:
  LOCAL_MODE=1 python tools/devices_cli.py enroll --device DEV-001 --pubkey device_pub.pem
"""
import os, sys, json, sqlite3, argparse, pathlib

LOCAL_MODE = os.environ.get("LOCAL_MODE","0")=="1"
BASE = pathlib.Path(os.environ.get("LOCAL_DATA_DIR","./local_data")).resolve()
DEVICES_TABLE = os.environ.get("DEVICES_TABLE","")
PUBLIC_KEY_S3_URI = os.environ.get("PUBLIC_KEY_S3_URI","")

def _s3_ck():
    import boto3
    s3=boto3.client("s3")
    return s3

def _parse_s3(uri):
    assert uri.startswith("s3://")
    b,k=uri[5:].split("/",1); return b,k

def _sqlite_conn():
    BASE.mkdir(parents=True, exist_ok=True)
    db=sqlite3.connect(BASE/"cases.db")
    db.execute("""create table if not exists devices(device_id text primary key, public_key_pem text, updated_at text)""")
    db.commit(); return db

def _now():
    import datetime as dt
    return dt.datetime.utcnow().isoformat()+"Z"

def _ddb_tbl():
    import boto3
    ddb=boto3.resource("dynamodb"); return ddb.Table(DEVICES_TABLE)

def s3_get_json():
    b,k=_parse_s3(PUBLIC_KEY_S3_URI); s3=_s3_ck()
    try:
        obj=s3.get_object(Bucket=b, Key=k)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except s3.exceptions.NoSuchKey:
        return {}

def s3_put_json(d):
    b,k=_parse_s3(PUBLIC_KEY_S3_URI); s3=_s3_ck()
    s3.put_object(Bucket=b, Key=k, Body=json.dumps(d).encode("utf-8"), ContentType="application/json")

def cmd_list():
    if LOCAL_MODE:
        db=_sqlite_conn(); rows=db.execute("select device_id, substr(public_key_pem,1,32)||'...' from devices").fetchall()
        for r in rows: print(r[0], r[1]); return
    if DEVICES_TABLE:
        tbl=_ddb_tbl(); resp=tbl.scan(ProjectionExpression="device_id, public_key_pem")
        for it in resp.get("Items",[]): print(it["device_id"], it["public_key_pem"][:32]+"..."); return
    if PUBLIC_KEY_S3_URI:
        mp=s3_get_json()
        for dev,pem in mp.items(): print(dev, pem[:32]+"..."); return
    print("No storage configured.")

def cmd_enroll(device, pubpath):
    pem=pathlib.Path(pubpath).read_text()
    if LOCAL_MODE:
        db=_sqlite_conn(); db.execute("insert or replace into devices(device_id, public_key_pem, updated_at) values(?,?,?)",(device,pem,_now())); db.commit(); print("OK (sqlite)"); return
    if DEVICES_TABLE:
        _ddb_tbl().put_item(Item={"device_id":device,"public_key_pem":pem,"updated_at":_now()}); print("OK (ddb)"); return
    if PUBLIC_KEY_S3_URI:
        mp=s3_get_json(); mp[device]=pem; s3_put_json(mp); print("OK (s3 json)"); return
    print("No storage configured.")

def cmd_revoke(device):
    if LOCAL_MODE:
        db=_sqlite_conn(); db.execute("delete from devices where device_id=?",(device,)); db.commit(); print("Revoked (sqlite)"); return
    if DEVICES_TABLE:
        _ddb_tbl().delete_item(Key={"device_id":device}); print("Revoked (ddb)"); return
    if PUBLIC_KEY_S3_URI:
        mp=s3_get_json(); mp.pop(device,None); s3_put_json(mp); print("Revoked (s3 json)"); return
    print("No storage configured.")

def main():
    ap=argparse.ArgumentParser()
    sub=ap.add_subparsers(dest="cmd", required=True)
    s=sub.add_parser("list")
    s=sub.add_parser("enroll"); s.add_argument("--device", required=True); s.add_argument("--pubkey", required=True)
    s=sub.add_parser("rotate"); s.add_argument("--device", required=True); s.add_argument("--pubkey", required=True)
    s=sub.add_parser("revoke"); s.add_argument("--device", required=True)
    args=ap.parse_args()
    if args.cmd=="list": return cmd_list()
    if args.cmd in ("enroll","rotate"): return cmd_enroll(args.device, args.pubkey)
    if args.cmd=="revoke": return cmd_revoke(args.device)

if __name__=="__main__":
    main()
