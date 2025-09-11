from __future__ import annotations
import json, hashlib
from typing import Dict, Any

def canonical_json(data: Dict[str, Any]) -> bytes:
    filtered = {k: v for k, v in data.items() if v is not None}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode()

def sha256_hex(data: Dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data)).hexdigest()

try:
    from nacl.signing import SigningKey, VerifyKey
    _HAS_NACL = True
except Exception:
    _HAS_NACL = False

def generate_keypair() -> Dict[str, str]:
    if not _HAS_NACL:
        raise RuntimeError("PyNaCl not installed")
    sk = SigningKey.generate()
    pk = sk.verify_key
    return {"private_key_hex": sk.encode().hex(), "public_key_hex": pk.encode().hex()}

def sign_payload(payload: Dict[str, Any], private_key_hex: str) -> str:
    if not _HAS_NACL:
        raise RuntimeError("PyNaCl not installed")
    sk = SigningKey(bytes.fromhex(private_key_hex))
    sig = sk.sign(canonical_json(payload)).signature
    return sig.hex()

def verify_signature(payload: Dict[str, Any], signature_hex: str, public_key_hex: str) -> bool:
    if not _HAS_NACL:
        return False
    try:
        vk = VerifyKey(bytes.fromhex(public_key_hex))
        vk.verify(canonical_json(payload), bytes.fromhex(signature_hex))
        return True
    except Exception:
        return False
