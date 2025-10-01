#!/usr/bin/env python3
"""
Create & sign a Calibration Record (v1).
Writes JSON to stdout or file.

Usage:
  python tools/calibration_cli.py --device AVSAFE-123 --operator me \
    --slm "NTi Audio,XL2,XL2-123456,Class-1,IEC 61672" \
    --flicker "Uprtek,MK350N,MK350-98765" \
    --firmware 1.3.2 --config 2025-09-01 \
    --out calib.json --sign-key private_key.pem
"""
import argparse, json, os, uuid, datetime as dt, base64, hashlib
from avsafe_descriptors.integrity.signing import sign_bytes

def parse_csv(x):
    return [p.strip() for p in x.split(",")]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--device", required=True)
    ap.add_argument("--operator", required=True)
    ap.add_argument("--slm", required=True, help="make,model,serial,class,standard")
    ap.add_argument("--flicker", required=True, help="make,model,serial")
    ap.add_argument("--firmware", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default="-")
    ap.add_argument("--sign-key", help="PEM file for Ed25519 signing")
    args=ap.parse_args()

    calib_id=str(uuid.uuid4())
    slm_m,slm_mod,slm_ser,slm_cls,slm_std=parse_csv(args.slm)
    fk_m,fk_mod,fk_ser=parse_csv(args.flicker)

    rec={
      "calibration_id": calib_id,
      "device_id": args.device,
      "timestamp": dt.datetime.utcnow().isoformat()+"Z",
      "operator": args.operator,
      "firmware_version": args.firmware,
      "config_version": args.config,
      "references":{
        "slm":{"make":slm_m,"model":slm_mod,"serial":slm_ser,"class":slm_cls,"standard":slm_std},
        "flicker_meter":{"make":fk_m,"model":fk_mod,"serial":fk_ser}
      },
      "audio_checks":{"mic_sensitivity_mV_per_Pa": None,"weighting_verified":{},"precheck":[],"postcheck":[]},
      "light_checks":{"precheck":[],"postcheck":[]},
      "environment":{}
    }

    payload=json.dumps(rec, separators=(",",":"), ensure_ascii=False).encode("utf-8")
    rec["content_hash"]=hashlib.sha256(payload).hexdigest()

    if args.sign_key and os.path.exists(args.sign_key):
        with open(args.sign_key,"rb") as f: pem=f.read()
        sig_block=sign_bytes(payload, private_key_pem=pem)
        rec.update({"sig":sig_block["sig_b64"], "alg":"ed25519"})
    else:
        rec.update({"sig":"","alg":"ed25519"})

    out=json.dumps(rec, ensure_ascii=False, indent=2)
    if args.out=="-":
        print(out)
    else:
        with open(args.out,"w",encoding="utf-8") as g: g.write(out)
        print(f"Wrote {args.out} (calibration_id={calib_id})")

if __name__=="__main__":
    main()
