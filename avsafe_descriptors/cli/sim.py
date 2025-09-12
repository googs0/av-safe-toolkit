#!/usr/bin/env python3
"""
AV-SAFE: Minute-summary simulator CLI

Generates privacy-preserving per-minute descriptors (audio + light) with a cryptographic
hash chain and optional signatures. Bands are generated as a pinkish spectrum and scaled
to match target LAeq (when A-weighting helper is available).

Examples
--------
  avsafe-sim --minutes 60 --outfile data/minutes.jsonl
  avsafe-sim --minutes 120 --start 2025-09-12T10:00:00Z --seed 42 --sign
  avsafe-sim --minutes 30 --third-range 100-5000 --audio-spike "t=10,dur=3,delta=8"
  avsafe-sim --minutes 90 --stdout --device-id DEV-001

Notes
-----
- Output is JSON Lines (one JSON object per line).
- Timestamps are UTC ISO 8601 with 'Z' suffix.
- Signatures are of the canonical JSON payload (not including the 'chain' block).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import random
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

# ---- Imports from project (optional for nicer realism) ----
try:
    # Prefer your pro-grade utilities if present
    from ..dsp.third_octave import nominal_centers as _nominal_centers
    from ..dsp.a_weighting import overall_level_dba as _overall_level_dba
except Exception:
    _nominal_centers = None
    _overall_level_dba = None

try:
    from ..integrity.hash_chain import chain_hash, canonical_json  # type: ignore
    from ..integrity.signing import sign_bytes  # type: ignore
except Exception as e:  # pragma: no cover
    print("FATAL: cannot import integrity utilities.", file=sys.stderr)
    raise

EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_RUNTIME = 1


# ----------------------- helpers -----------------------

def _parse_iso_utc(s: Optional[str]) -> dt.datetime:
    """Parse ISO8601; default to now (UTC). Always return an aware UTC dt."""
    if not s or s.lower() == "now":
        return dt.datetime.now(dt.timezone.utc)
    # Accept 'Z' or offset
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def _utc_iso(dt_utc: dt.datetime) -> str:
    return dt_utc.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _default_third_centers(fmin: float, fmax: float) -> List[float]:
    """Nominal IEC 1/3-oct centers between fmin..fmax (Hz). Fallback to a small list if dsp module missing."""
    if _nominal_centers is not None:
        return [float(x) for x in _nominal_centers(fmin_hz=fmin, fmax_hz=fmax)]
    # Fallback conservative set
    base = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
            200, 250, 315, 400, 500, 630, 800, 1000,
            1250, 1600, 2000, 2500, 3150, 4000, 5000]
    return [float(x) for x in base if fmin <= x <= fmax]


def _pinkish_spectrum(centers: Sequence[float], laeq_target: float, rng: random.Random) -> Dict[str, float]:
    """
    Create a pinkish 1/3-oct spectrum around a target LAeq (dB). If A-weighting is available,
    scale so that the A-weighted sum matches the target LAeq. Otherwise, just return a plausible shape.
    """
    # Build an initial slope around 1 kHz: ~ -3 dB/oct, with a bit of jitter
    # Compute per-band base levels
    levels = []
    for fc in centers:
        octaves_from_1k = math.log2(fc / 1000.0)
        base = laeq_target - 6.0 * octaves_from_1k + rng.gauss(0.0, 1.5)
        levels.append(base)

    # If we can compute A-weighted sum, scale to match target
    if _overall_level_dba is not None:
        computed = _overall_level_dba(levels, centers)
        if computed != float("-inf"):
            delta = laeq_target - computed
            levels = [L + delta for L in levels]

    return {str(int(round(c))) if c >= 100 else str(round(c, 1)): round(L, 1)
            for c, L in zip(centers, levels)}


def _apply_audio_spike(laeq: float, spike: Optional[Tuple[int, int, float]], idx: int) -> float:
    """If within spike window, add delta dB to LAeq (simple model)."""
    if not spike:
        return laeq
    t0, dur, delta = spike
    return laeq + (delta if t0 <= idx < t0 + dur else 0.0)


def _apply_flicker_spike(mod_percent: float, spike: Optional[Tuple[int, int, float]], idx: int) -> float:
    """If within spike window, add delta percentage points to Mod%."""
    if not spike:
        return mod_percent
    t0, dur, delta = spike
    return mod_percent + (delta if t0 <= idx < t0 + dur else 0.0)


def _parse_spike(s: Optional[str]) -> Optional[Tuple[int, int, float]]:
    """
    Parse spike spec like: "t=10,dur=3,delta=8" -> (10, 3, 8.0)
    Returns None if not provided.
    """
    if not s:
        return None
    parts = dict(pair.split("=", 1) for pair in s.split(","))
    t = int(parts.get("t", "0"))
    dur = int(parts.get("dur", "1"))
    delta = float(parts.get("delta", "6"))
    if t < 0 or dur <= 0:
        raise ValueError("--audio-spike/--flicker-spike must have t>=0 and dur>0")
    return (t, dur, delta)


def _ensure_out_path(path: Path, overwrite: bool) -> None:
    parent = (Path.cwd() / path).parent if not path.is_absolute() else path.parent
    parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Output exists: {path}. Use --overwrite to replace.")


# ----------------------- main generation -----------------------

def gen_minute_record(
    idx: int,
    ts_utc: dt.datetime,
    prev_hash: Optional[str],
    rng: random.Random,
    centers: Sequence[float],
    laeq_base: float,
    laeq_sigma: float,
    lcpeak_extra_range: Tuple[float, float],
    tlm_freq_choices: Sequence[float],
    tlm_mod_base: float,
    tlm_mod_sigma: float,
    flicker_index_range: Tuple[float, float],
    audio_spike: Optional[Tuple[int, int, float]],
    flicker_spike: Optional[Tuple[int, int, float]],
    device_id: Optional[str],
    schema: str,
    sign: bool,
) -> dict:
    # Base LAeq and spectrum
    laeq = rng.gauss(laeq_base, laeq_sigma)
    laeq = _apply_audio_spike(laeq, audio_spike, idx)
    bands = _pinkish_spectrum(centers, laeq, rng)

    # LCpeak offset
    lcpeak = laeq + rng.uniform(*lcpeak_extra_range)

    # Flicker path
    tlm_f = float(rng.choice(tlm_freq_choices))
    tlm_mod = max(0.0, rng.gauss(tlm_mod_base, tlm_mod_sigma))
    tlm_mod = _apply_flicker_spike(tlm_mod, flicker_spike, idx)
    flicker_index = round(rng.uniform(*flicker_index_range), 3)

    # Payload
    payload = {
        "schema": schema,
        "idx": idx,
        "ts": _utc_iso(ts_utc),
        "device_id": device_id,
        "audio": {
            "laeq_db": round(laeq, 1),
            "lcpeak_db": round(lcpeak, 1),
            "third_octave_db": bands,
        },
        "light": {
            "tlm_freq_hz": tlm_f,
            "tlm_mod_percent": round(tlm_mod, 2),
            "flicker_index": flicker_index,
        },
    }

    # Chain & sign
    h = chain_hash(prev_hash, payload)
    record = payload | {"chain": {"hash": h}}
    if sign:
        sig_block = sign_bytes(canonical_json(payload).encode("utf-8"))
        record["chain"] |= sig_block
    return record


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="avsafe-sim",
        description="Generate AV-SAFE minute summaries (JSONL) with hash chaining and optional signatures.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  avsafe-sim --minutes 60 --outfile data/minutes.jsonl\n"
            "  avsafe-sim --minutes 120 --start 2025-09-12T10:00:00Z --seed 42 --sign\n"
            "  avsafe-sim --minutes 30 --third-range 100-5000 --audio-spike t=10,dur=3,delta=8\n"
            "  avsafe-sim --minutes 90 --stdout --device-id DEV-001\n"
        ),
    )
    p.add_argument("--minutes", type=int, default=60, help="Number of minute records to generate. Default: 60")
    p.add_argument("--start", type=str, default="now", help="Start time (ISO8601, e.g., 2025-09-12T10:00:00Z). Default: now")
    out_group = p.add_mutually_exclusive_group()
    out_group.add_argument("--outfile", type=str, default="minutes.jsonl", help="Output JSONL path. Default: minutes.jsonl")
    out_group.add_argument("--stdout", action="store_true", help="Write to stdout instead of a file.")
    p.add_argument("--overwrite", action="store_true", help="Allow overwriting an existing outfile.")
    p.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility.")
    p.add_argument("--sign", action="store_true", help="Sign each payload (ed25519 via integrity.signing).")
    p.add_argument("--device-id", type=str, default=None, help="Optional device identifier to embed in each record.")
    p.add_argument("--schema", type=str, default="avsafe.v1", help="Schema/version tag to embed. Default: avsafe.v1")

    # Audio model knobs
    p.add_argument("--laeq-base", type=float, default=52.0, help="Baseline LAeq mean (dB). Default: 52.0")
    p.add_argument("--laeq-sigma", type=float, default=4.0, help="LAeq Gaussian sigma (dB). Default: 4.0")
    p.add_argument("--lcpeak-extra", type=str, default="5,15",
                   help="Uniform extra dB over LAeq for LCpeak as 'min,max'. Default: '5,15'")

    # Bands
    p.add_argument("--third-bands", type=str, default=None,
                   help="Comma-separated nominal centers (e.g., '125,250,500,1000,2000').")
    p.add_argument("--third-range", type=str, default="100-5000",
                   help="Generate nominal 1/3-oct centers in this Hz range (e.g., '100-5000'). Ignored if --third-bands is set.")

    # Light model knobs
    p.add_argument("--tlm-freqs", type=str, default="100,120,180,300,1000",
                   help="Comma-separated TLM frequencies to sample from (Hz).")
    p.add_argument("--tlm-mod-base", type=float, default=2.0, help="Baseline modulation depth mean (percent). Default: 2.0")
    p.add_argument("--tlm-mod-sigma", type=float, default=1.0, help="Modulation depth sigma (percent points). Default: 1.0")
    p.add_argument("--flicker-index", type=str, default="0.00,0.20",
                   help="Uniform range for flicker index as 'min,max'. Default: '0.00,0.20'")

    # Scenario spikes
    p.add_argument("--audio-spike", type=str, default=None,
                   help="Inject LAeq spike: 't=<start>,dur=<minutes>,delta=<dB>' (e.g., 't=10,dur=3,delta=8').")
    p.add_argument("--flicker-spike", type=str, default=None,
                   help="Inject Mod%% spike: 't=<start>,dur=<minutes>,delta=<percent>'.")

    p.add_argument("--verbose", action="store_true", help="Verbose tracebacks on errors.")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    # RNG
    rng = random.Random(args.seed)

    # Parse time
    try:
        start_utc = _parse_iso_utc(args.start)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: bad --start value: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Bands
    try:
        if args.third_bands:
            centers = [float(x.strip()) for x in args.third_bands.split(",") if x.strip()]
        else:
            lo, hi = (float(x) for x in args.third_range.split("-", 1))
            centers = _default_third_centers(lo, hi)
        if not centers:
            raise ValueError("No 1/3-octave centers resolved.")
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: parsing bands: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Other knobs
    try:
        lc_min, lc_max = (float(x) for x in args.lcpeak_extra.split(",", 1))
        fi_min, fi_max = (float(x) for x in args.flicker_index.split(",", 1))
        tlm_freqs = [float(x.strip()) for x in args.tlm_freqs.split(",") if x.strip()]
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: parsing numeric ranges: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Spikes
    try:
        audio_spike = _parse_spike(args.audio_spike)
        flicker_spike = _parse_spike(args.flicker_spike)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: spike spec: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Output
    if not args.stdout:
        out_path = Path(args.outfile).expanduser()
        try:
            _ensure_out_path(out_path, overwrite=args.overwrite)
        except Exception as e:
            if args.verbose:
                traceback.print_exc()
            print(f"ERROR: {e}", file=sys.stderr)
            return EXIT_BAD_ARGS

    # Generate
    prev_hash: Optional[str] = None
    try:
        if args.stdout:
            out_f = sys.stdout
            close_needed = False
        else:
            out_f = open(out_path, "w", encoding="utf-8")
            close_needed = True

        with out_f:
            for i in range(int(args.minutes)):
                ts = start_utc + dt.timedelta(minutes=i)
                rec = gen_minute_record(
                    idx=i,
                    ts_utc=ts,
                    prev_hash=prev_hash,
                    rng=rng,
                    centers=centers,
                    laeq_base=args.laeq_base,
                    laeq_sigma=args.laeq_sigma,
                    lcpeak_extra_range=(lc_min, lc_max),
                    tlm_freq_choices=tlm_freqs,
                    tlm_mod_base=args.tlm_mod_base,
                    tlm_mod_sigma=args.tlm_mod_sigma,
                    flicker_index_range=(fi_min, fi_max),
                    audio_spike=audio_spike,
                    flicker_spike=flicker_spike,
                    device_id=args.device_id,
                    schema=args.schema,
                    sign=args.sign,
                )
                prev_hash = rec["chain"]["hash"]
                out_f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        if not args.stdout:
            print(f"Wrote {args.minutes} minutes to {out_path}")

    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: generation failed: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
