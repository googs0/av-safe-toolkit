"""
Local pipeline runner: scans ./local_data/<RAW_BUCKET>/raw/* and
runs verify -> rules -> report using the same code path as the Lambdas.

Usage:
  LOCAL_MODE=1 python -m cloud.local_runner --once
  LOCAL_MODE=1 python -m cloud.local_runner --watch   # naive loop
"""
import os, time, json, pathlib, argparse
from cloud.common import (
    LOCAL_MODE, BASE, RAW_BUCKET, VERIFIED_BUCKET, REPORTS_BUCKET,
    get_object_bytes, put_object_bytes, read_jsonl_bytes, jsonl_bytes,
    load_pubkey_map, verify_minutes_chain_and_signatures,
    run_rules_and_report, update_case_status,
)

RAW_DIR = (BASE / RAW_BUCKET / "raw")
VER_DIR = (BASE / VERIFIED_BUCKET / "verified")
REP_DIR = (BASE / REPORTS_BUCKET / "reports")

def process_once() -> int:
    count = 0
    for gz in RAW_DIR.rglob("minutes.jsonl.gz"):
        # raw/{case}/{ts}/minutes.jsonl.gz
        parts = gz.parts[-4:]
        if len(parts) != 4: continue
        _, case_id, ts_folder, _ = parts
        # skip if already processed
        out_min = VER_DIR / case_id / ts_folder / "minutes.jsonl"
        if out_min.exists(): continue

        blob = gz.read_bytes()
        minutes = read_jsonl_bytes(blob)
        ver = verify_minutes_chain_and_signatures(minutes, load_pubkey_map())

        (VER_DIR / case_id / ts_folder).mkdir(parents=True, exist_ok=True)
        (REP_DIR / case_id / ts_folder).mkdir(parents=True, exist_ok=True)

        (VER_DIR / case_id / ts_folder / "verification.json").write_bytes(json.dumps(ver).encode("utf-8"))
        out_min.write_bytes(jsonl_bytes(minutes))

        status = "verified_ok" if ver.get("ok") else f"break_at_{ver.get('break_index')}"
        update_case_status(case_id, status=status, last_ts=ts_folder,
                           last_verified_key=f"verified/{case_id}/{ts_folder}/minutes.jsonl")

        if ver.get("ok"):
            results, html = run_rules_and_report(minutes)
            (REP_DIR / case_id / ts_folder / "results.json").write_bytes(json.dumps(results).encode("utf-8"))
            (REP_DIR / case_id / ts_folder / "report.html").write_bytes(html)
            update_case_status(case_id, status="reported",
                               last_report=f"reports/{case_id}/{ts_folder}/report.html", last_ts=ts_folder)
        count += 1
    return count

def main():
    if not LOCAL_MODE:
        print("LOCAL_MODE=1 required for local runner.", flush=True); return
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    args = ap.parse_args()
    if args.once:
        n = process_once(); print(f"Processed {n} new upload(s).")
    elif args.watch:
        print("Watching for new uploads...")
        while True:
            n = process_once()
            if n: print(f"Processed {n} new upload(s).")
            time.sleep(2)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
