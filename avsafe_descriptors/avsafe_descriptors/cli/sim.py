
from __future__ import annotations
import argparse, json, random, datetime, os
from ..integrity.hash_chain import chain_hash, canonical_json
from ..integrity.signing import sign_bytes

def gen_minute(idx: int, prev_hash: str | None, sign: bool) -> dict:
    ts = (datetime.datetime.utcnow() + datetime.timedelta(minutes=idx)).isoformat() + "Z"
    laeq = random.gauss(52, 4)  # dB
    lcpeak = laeq + random.uniform(5, 15)
    third = {str(b): round(random.gauss(40, 5), 1) for b in [125, 250, 500, 1000, 2000]}
    tlm_f = random.choice([100, 120, 180, 300, 1000])
    tlm_mod = max(0.1, random.gauss(2.0, 1.0))  # percent
    flicker_index = round(random.uniform(0.0, 0.2), 3)

    payload = {
        "idx": idx, "ts": ts,
        "audio": {"laeq_db": round(laeq,1), "lcpeak_db": round(lcpeak,1), "third_octave_db": third},
        "light": {"tlm_freq_hz": tlm_f, "tlm_mod_percent": round(tlm_mod,2), "flicker_index": flicker_index},
    }
    h = chain_hash(prev_hash, payload)
    record = payload | {"chain": {"hash": h}}
    if sign:
        sig = sign_bytes(canonical_json(payload).encode("utf-8"))
        record["chain"] |= sig
    return record

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--outfile", type=str, default="minutes.jsonl")
    ap.add_argument("--sign", action="store_true")
    args = ap.parse_args()

    prev = None
    with open(args.outfile, "w", encoding="utf-8") as f:
        for i in range(args.minutes):
            rec = gen_minute(i, prev, args.sign)
            prev = rec["chain"]["hash"]
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"Wrote {args.minutes} minutes to {args.outfile}")

if __name__ == "__main__":
    main()
