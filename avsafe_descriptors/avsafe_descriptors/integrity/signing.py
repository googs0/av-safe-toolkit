
from __future__ import annotations
from typing import Optional

def sign_bytes(data: bytes, private_key_hex: Optional[str] = None) -> dict:
    """Sign bytes using Ed25519 if PyNaCl is available; otherwise return HMAC-like SHA256 placeholder.
    Returns dict with 'scheme', 'signature_hex', and 'public_key_hex' (if applicable).
    """
    try:
        from nacl.signing import SigningKey
    except Exception:
        import hashlib
        # WARNING: Placeholder, not cryptographically strong. For demo only.
        secret = (private_key_hex or "demo-secret").encode('utf-8')
        sig = hashlib.sha256(secret + data).hexdigest()
        return {"scheme": "sha256-demo", "signature_hex": sig, "public_key_hex": None}

    if private_key_hex is None:
        sk = SigningKey.generate()
    else:
        sk = SigningKey(bytes.fromhex(private_key_hex))
    signed = sk.sign(data)
    pk = sk.verify_key
    return {"scheme": "ed25519", "signature_hex": signed.signature.hex(), "public_key_hex": pk.encode().hex()}
