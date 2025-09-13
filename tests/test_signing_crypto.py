# tests/test_signing_crypto.py
from __future__ import annotations

import os
import binascii
import pytest


def _has_nacl() -> bool:
    try:
        import nacl.signing  # noqa: F401
        return True
    except Exception:
        return False


def test_sign_uses_real_crypto_or_skips(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    In strict mode, we require real Ed25519 signatures.
    If the Ed25519 backend (PyNaCl) truly isn't available in this env, skip the test.
    """
    monkeypatch.setenv("AVSAFE_STRICT_CRYPTO", "1")

    # Import after env var is set
    from avsafe_descriptors.integrity.signing import sign_bytes  # type: ignore

    try:
        sig = sign_bytes(b"test-message")
    except RuntimeError:
        # Ed25519 not available in this environment → acceptable to skip
        pytest.skip("PyNaCl/Ed25519 not available in this environment")

    assert isinstance(sig, dict)
    assert sig.get("scheme") == "ed25519"
    assert isinstance(sig.get("signature_hex"), str) and len(sig["signature_hex"]) == 128  # 64 bytes → 128 hex
    assert isinstance(sig.get("public_key_hex"), str) and len(sig["public_key_hex"]) == 64   # 32 bytes → 64 hex


@pytest.mark.skipif(not _has_nacl(), reason="PyNaCl not available to verify Ed25519 or derive pubkey")
def test_deterministic_with_fixed_private_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    With a fixed private key, Ed25519 signatures are deterministic for the same message.
    Also confirm the returned public key matches the private key's derived public key.
    """
    from nacl.signing import SigningKey  # type: ignore

    monkeypatch.setenv("AVSAFE_STRICT_CRYPTO", "1")

    # 32-byte test key (hex). This is a NON-SECRET placeholder for tests.
    # Do not use in production. Length must be exactly 64 hex chars.
    test_priv_hex = "0123456789abcdeffedcba98765432100123456789abcdeffedcba9876543210"
    monkeypatch.setenv("AVSAFE_PRIV_HEX", test_priv_hex)

    # Import after env vars are set so the module reads them
    from avsafe_descriptors.integrity.signing import sign_bytes  # type: ignore

    msg1 = b"same-message"
    msg2 = b"another-message"

    sig1 = sign_bytes(msg1)
    sig1_again = sign_bytes(msg1)
    sig2 = sign_bytes(msg2)

    # Deterministic for same message with same private key
    assert sig1["signature_hex"] == sig1_again["signature_hex"]
    # Different message → different signature
    assert sig1["signature_hex"] != sig2["signature_hex"]

    # Public key correctness: derive from the private key and compare
    sk = SigningKey(binascii.unhexlify(test_priv_hex))
    expected_pk_hex = sk.verify_key.encode().hex()
    assert sig1["public_key_hex"] == expected_pk_hex

    # Basic shape checks
    assert sig1["scheme"] == "ed25519"
    assert len(sig1["public_key_hex"]) == 64
    assert len(sig1["signature_hex"]) == 128
