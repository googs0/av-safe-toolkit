from __future__ import annotations
import argparse, json, random
from datetime import datetime, timedelta, timezone
from avsafe_descriptors.io.minute_summary import MinuteSummary
from avsafe_descriptors.integrity.integrity import sha256_hex, generate_keypair, sign_payload

def synth_laeq(hour: int) -> float:
    base = 40 if (hour >= 22 or hour < 7) else 52
    return base + random.uniform(-3, 6)

def synth_tlm(hour: int) -> tuple[float, float, float]:
    if 8 <= hour <= 18 and random.random() < 0.2:
        f = random.choice([100.0, 120.0, 150.0])
        pm = random.uniform(20.0, 60.0)
        fi = min(0.5, pm/100.0 * 0.6)
    else:
        f = random.choice([100.0, 120.0])
        pm = random.uniform(2.0, 15.0)
        fi = pm/100.0 * 0.3
    return (f, pm, fi)

def main():
    ap = argparse.ArgumentParser(description="Generate AV-SAFE minute summaries (JSONL)")
    ap.add_argument("--start", type=str, default=None, help="UTC start ISO, default now")
    ap.add_argument("--minutes", type=int, default=60*24)
    ap.add_argument("--outfile", type=str, default="minutes.jsonl")
    ap.add_argument("--sign", action="store_true")
    args = ap.parse_args()

    if args.start:
        start = datetime.fromisoformat(args.start.replace("Z","+00:00")).astimezone(timezone.utc)
    else:
        start = datetime.now(timezone.utc).replace(second=0, microsecond=0)

    public_key_hex = None; private_key_hex = None
    if args.sign:
        kp = generate_keypair()
        print(f"# public_key_hex={kp['public_key_hex']}")
        print(f"# private_key_hex={kp['private_key_hex']}  # keep this secret")
        public_key_hex = kp["public_key_hex"]; private_key_hex = kp["private_key_hex"]

    prev_hash = None; n = 0
    with open(args.outfile, "w") as f:
        for i in range(args.minutes):
            ts = start + timedelta(minutes=i)
            laeq = synth_laeq(ts.hour)
            fdom, pm, fi = synth_tlm(ts.hour)
            minute = MinuteSummary(timestamp_utc=ts, laeq_db=laeq, tlm_f_dom_hz=fdom, tlm_percent_mod=pm, tlm_flicker_index=fi, prev_hash=prev_hash)
            payload = minute.model_dump()
            payload_no_sig = dict(payload); payload_no_sig.pop("signature", None)
            local_hash = sha256_hex(payload_no_sig)
            if private_key_hex:
                payload["signature"] = sign_payload(payload_no_sig, private_key_hex)
            f.write(json.dumps(payload, default=str) + "\n")
            prev_hash = local_hash; n += 1
    print(f"Wrote {n} minutes -> {args.outfile}")

if __name__ == "__main__":
    main()
