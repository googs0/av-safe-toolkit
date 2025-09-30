#!/usr/bin/env python3
"""
Create a case -> request an upload URL -> upload minutes.jsonl.gz.
Works with:
  - local dev: uvicorn cloud.api_app:app (AUTH_MODE=dev, DEV_TOKEN=... , LOCAL_MODE=1)
  - Lambda Function URL (same headers)
Usage:
  python tools/client_uploader.py --base http://127.0.0.1:8000 --token devtoken \
      --label "Test Case" --device DEV-001 --file minutes.jsonl.gz
"""
import argparse, json, sys, shutil, urllib.parse, pathlib, requests

def is_file_url(u: str) -> bool:
    return urllib.parse.urlparse(u).scheme == "file"

def upload_file(url: str, path: pathlib.Path, token: str):
    if is_file_url(url):
        dst = pathlib.Path(urllib.parse.urlparse(url).path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dst)
        return {"ok": True, "local_path": str(dst)}
    # otherwise PUT to presigned URL
    with path.open("rb") as f:
        r = requests.put(url, data=f, headers={"Content-Type":"application/gzip"})
        r.raise_for_status()
        return {"ok": True, "http_status": r.status_code}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="API base, e.g. http://127.0.0.1:8000 or Function URL")
    ap.add_argument("--token", required=True, help="Bearer token (DEV_TOKEN)")
    ap.add_argument("--label", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--file",   required=True)
    args = ap.parse_args()

    headers = {"Authorization": f"Bearer {args.token}", "Content-Type":"application/json"}

    # 1) create case
    r = requests.post(args.base.rstrip("/") + "/cases", headers=headers, json={"label": args.label})
    r.raise_for_status()
    case_id = r.json()["case_id"]
    print("case_id:", case_id)

    # 2) ingest/start
    r = requests.post(args.base.rstrip("/") + "/ingest/start", headers=headers,
                      json={"case_id": case_id, "device_id": args.device, "filename": "minutes.jsonl.gz"})
    r.raise_for_status()
    info = r.json()
    print("upload target:", info["key"])

    # 3) upload
    res = upload_file(info["upload_url"], pathlib.Path(args.file), args.token)
    print("upload:", res)

    print("Done. If LOCAL_MODE=1, run:")
    print("  python -m cloud.local_runner --once")

if __name__ == "__main__":
    main()
