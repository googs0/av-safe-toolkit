#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Ed25519 signing helpers (drop-in, hardened).

- Primary API: sign_bytes(data: bytes, private_key_hex: str|None) -> dict
  Returns: {"scheme", "signature_hex", "public_key_hex"}

    * Prefers PyNaCl (libsodium)
    * Falls back to cryptography's Ed25519
    * Final fallback: SHA-256 "demo" MAC (NOT secure). Your pipeline still runs.

- Hardening:
    * Domain-separated payload signing via sign_payload(payload, key)
    * Strict mode: set AVSAFE_STRICT_CRYPTO=1 to disallow demo fallback
    * Optional stable seed: AVSAFE_PRIV_HEX="…64-hex…" (32-byte Ed25519)

Env:
    AVSAFE_PRIV_HEX        optional 64-hex seed (32B)
    AVSAFE_STRICT_CRYPTO   "1" to require real crypto libs
"""

from __future__ import annotations
from typing import Optional, Tuple
import os, hashlib

# Optional backends (lazy-checked)
_HAVE_NACL = False
_HAVE_CRYPTO = False
try:
    from nacl.signing import SigningKey as NaClSigningKey  # type: ignore
    from nacl.signing import VerifyKey as NaClVerifyKey    # type: ignore
    _HAVE_NACL = True
except Exception:
    pass

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey  # type: ignore
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat  # type: ignore
    _HAVE_CRYPTO = True
except Exception:
    pass

# Domain tag for payload signing
SIGN_DOMAIN = b"avsafe:sign:v1"

def _env_seed_hex() -> Optional[str]:
    return os.environ.get("AVSAFE_PRIV_HEX") or None

def _strict_crypto() -> bool:
    return os.environ.get("AVSAFE_STRICT_CRYPTO") == "1"

def _coerce_seed(seed_hex: str) -> bytes:
    raw = bytes.fromhex(seed_hex)
    if len(raw) == 32:
        return raw
    if len(raw) == 64:
        return raw[:32]
    raise ValueError("private_key_hex must be 32 or 64 bytes (64 or 128 hex chars)")

def _sign_nacl(data: bytes, priv_seed_hex: Optional[str]) -> Tuple[str, str]:
    if priv_seed_hex is None:
        sk = NaClSigningKey.generate()
    else:
        sk = NaClSigningKey(_coerce_seed(priv_seed_hex))
    sig_hex = sk.sign(data).signature.hex()
    pub_hex = sk.verify_key.encode().hex()
    return sig_hex, pub_hex

def _sign_crypto(data: bytes, priv_seed_hex: Optional[str]) -> Tuple[str, str]:
    if priv_seed_hex is None:
        sk = Ed25519PrivateKey.generate()
    else:
        sk = Ed25519PrivateKey.from_private_bytes(_coerce_seed(priv_seed_hex))
    sig_hex = sk.sign(data).hex()
    pub_hex = sk.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return sig_hex, pub_hex

def sign_bytes(data: bytes, private_key_hex: Optional[str] = None) -> dict:
    """
    Sign arbitrary bytes. If no key is provided:
      1) use AVSAFE_PRIV_HEX if set
      2) else generate an ephemeral key (valid sig, changes each run)

    Returns:
      {"scheme": "ed25519"|"sha256-demo", "signature_hex": "...", "public_key_hex": "... or None"}
    """
    seed_hex = private_key_hex or _env_seed_hex()

    if _HAVE_NACL:
        sig_hex, pub_hex = _sign_nacl(data, seed_hex)
        return {"scheme": "ed25519", "signature_hex": sig_hex, "public_key_hex": pub_hex}

    if _HAVE_CRYPTO:
        sig_hex, pub_hex = _sign_crypto(data, seed_hex)
        return {"scheme": "ed25519", "signature_hex": sig_hex, "public_key_hex": pub_hex}

    if _strict_crypto():
        raise RuntimeError("Real crypto required (set libsodium/PyNaCl or cryptography).")

    # LAST-RESORT FALLBACK (NOT CRYPTOGRAPHIC): still lets the simulator run.
    secret = (seed_hex or "demo-secret").encode("utf-8")
    sig = hashlib.sha256(secret + data).hexdigest()
    return {"scheme": "sha256-demo", "signature_hex": sig, "public_key_hex": None}

def verify_bytes(data: bytes, signature_hex: str, public_key_hex: Optional[str], scheme: str = "ed25519") -> bool:
    """
    Verify signature over bytes. Returns True/False.
    - For "ed25519": requires a crypto backend and public_key_hex.
    - For "sha256-demo": recomputes demo MAC with 'demo-secret' (local tests only).
    """
    scheme = scheme.lower()

    if scheme == "ed25519" and public_key_hex:
        if _HAVE_NACL:
            try:
                NaClVerifyKey(bytes.fromhex(public_key_hex)).verify(data, bytes.fromhex(signature_hex))
                return True
            except Exception:
                return False
        if _HAVE_CRYPTO:
            try:
                Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(bytes.fromhex(signature_hex), data)
                return True
            except Exception:
                return False
        return False

    if scheme == "sha256-demo":
        return hashlib.sha256(b"demo-secret" + data).hexdigest() == signature_hex

    return False

# Optional, domain-separated payload signing (recommended for records)
def sign_payload(payload: dict, private_key_hex: Optional[str] = None) -> dict:
    from .hash_chain import canonical_json
    msg = SIGN_DOMAIN + canonical_json(payload).encode("utf-8")
    return sign_bytes(msg, private_key_hex)

__all__ = ["sign_bytes", "verify_bytes", "sign_payload", "SIGN_DOMAIN"]
