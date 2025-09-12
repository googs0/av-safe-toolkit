#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Hash chaining utilities for tamper-evident minute summaries.

Key properties:
- Deterministic JSON canonicalization (UTF-8, sorted keys, no NaN).
- Domain-separated hashing to avoid collision reuse across contexts.
- Support for SHA-256 (default) and BLAKE2b-256.
- Helpers to create chain records and verify links/chains.

Usage (typical):
    prev = None
    for payload in minutes:  # payload: dict WITHOUT 'chain'
        record = make_record(payload, prev)   # adds {'chain': {...}}
        prev = record['chain']['hash']
        write_jsonl(record)

Verification:
    ok, idx, reason = verify_chain(iter_records())
    if not ok: raise ValueError(f"Chain break at {idx}: {reason}")
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple

# -------------------------
# Canonicalization
# -------------------------

def canonical_json(obj: Any) -> str:
    """
    Return a stable JSON string:
      - UTF-8, sorted keys
      - minimal separators
      - NaN/Infinity rejected (ensures cross-runtime consistency)
    """
    return json.dumps(
        obj,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

# -------------------------
# Hash selection & helpers
# -------------------------

_SUPPORTED = {"sha256", "blake2b"}

def _new_hasher(alg: str):
    alg = alg.lower()
    if alg == "sha256":
        return hashlib.sha256()
    if alg == "blake2b":
        # 32-byte digest (256-bit) for parity with sha256
        return hashlib.blake2b(digest_size=32)
    raise ValueError(f"Unsupported hash alg: {alg}. Supported: {_SUPPORTED}")

# A domain label mixed into every hash to prevent cross-protocol collisions.
# If you change this, bump the version suffix.
DOMAIN = b"avsafe:chain:v1"

# -------------------------
# Core API
# -------------------------

def chain_hash(
    prev_hex: Optional[str],
    payload: Dict[str, Any],
    *,
    alg: str = "sha256",
    domain: bytes = DOMAIN,
) -> str:
    """
    Compute a chain hash over (domain || prev_hash || canonical_json(payload)).

    - prev_hex: hex string of previous link's hash (or None for first link)
    - payload: dict WITHOUT 'chain' key
    - alg: 'sha256' (default) or 'blake2b'
    - returns hex digest string
    """
    h = _new_hasher(alg)
    h.update(domain)

    if prev_hex:
        try:
            h.update(bytes.fromhex(prev_hex))
        except ValueError as e:
            raise ValueError("prev_hex must be a valid hex digest") from e

    try:
        cj = canonical_json(payload)
    except ValueError as e:
        # Raised if payload contains NaN/Infinity
        raise ValueError(f"Payload is not JSON-canonicalizable: {e}") from e

    h.update(cj.encode("utf-8"))
    return h.hexdigest()


def make_record(
    payload: Dict[str, Any],
    prev_hex: Optional[str],
    *,
    alg: str = "sha256",
    include_prev: bool = True,
) -> Dict[str, Any]:
    """
    Return a new record that merges the given payload with a 'chain' block:
      {
        ...payload...,
        "chain": {
          "alg": "sha256",
          "hash": "<hex>",
          "prev": "<prev_hex-or-null>"
        }
      }

    Note: Hash is computed ONLY over the 'payload' (no 'chain' fields).
    """
    if "chain" in payload:
        raise ValueError("Payload must not contain a 'chain' key")

    digest = chain_hash(prev_hex, payload, alg=alg)
    chain_block: Dict[str, Any] = {"alg": alg, "hash": digest}
    if include_prev:
        chain_block["prev"] = prev_hex

    # Non-mutating merge (Python 3.9+)
    return payload | {"chain": chain_block}


def verify_link(
    prev_hex: Optional[str],
    record: Dict[str, Any],
    *,
    domain: bytes = DOMAIN,
) -> Tuple[bool, str]:
    """
    Verify a single record's chain linkage.

    Returns (ok, reason):
      - ok = True if valid
      - ok = False and reason explains mismatch

    Expects 'record' to contain a 'chain' dict with:
      - 'hash': expected digest (hex)
      - 'alg': name ('sha256' or 'blake2b'); default 'sha256' if missing
      - optional 'prev': previous hash (checked against prev_hex if present)
    """
    if "chain" not in record or not isinstance(record["chain"], dict):
        return False, "missing or invalid 'chain' block"

    ch = record["chain"]
    expected = ch.get("hash")
    alg = ch.get("alg", "sha256")
    rec_prev = ch.get("prev", None)

    if expected is None or not isinstance(expected, str):
        return False, "missing expected hash"

    if rec_prev is not None and prev_hex is not None and rec_prev != prev_hex:
        return False, "prev pointer does not match provided prev hash"

    # Recompute over the *payload* (record without 'chain')
    payload = {k: v for k, v in record.items() if k != "chain"}
    try:
        recomputed = chain_hash(prev_hex, payload, alg=alg, domain=domain)
    except Exception as e:
        return False, f"recompute failed: {e}"

    if recomputed != expected:
        return False, "digest mismatch"

    return True, "ok"


def verify_chain(
    records: Iterable[Dict[str, Any]],
    *,
    domain: bytes = DOMAIN,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Verify a sequence of chain records, in order.

    Returns (ok, index, reason):
      - ok=True  -> entire sequence valid; index=None; reason=None
      - ok=False -> first failing record index and reason
    """
    prev: Optional[str] = None
    for idx, rec in enumerate(records):
        ok, reason = verify_link(prev, rec, domain=domain)
        if not ok:
            return False, idx, reason
        prev = rec["chain"]["hash"]
    return True, None, None


__all__ = [
    "canonical_json",
    "chain_hash",
    "make_record",
    "verify_link",
    "verify_chain",
    "DOMAIN",
]
