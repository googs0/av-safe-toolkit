# tests/test_hash_chain.py
from __future__ import annotations

import hashlib
import json
import string
import random
import pytest

from avsafe_descriptors.integrity.hash_chain import (
    canonical_json,
    chain_hash,
)


def test_canonical_json_sorts_keys_and_is_stable():
    """Different key orders must serialize identically."""
    a = {"b": 2, "a": 1}
    b = {"a": 1, "b": 2}
    sa = canonical_json(a)
    sb = canonical_json(b)
    assert sa == sb
    # Spot-check formatting choices: compact separators and UTF-8 (ensure_ascii=False)
    assert ",\"" in sa  # compact separators (`,` without spaces)
    # Confirm round-trip is identical data
    assert json.loads(sa) == json.loads(sb) == {"a": 1, "b": 2}


def test_canonical_json_unicode_is_deterministic():
    """Unicode content should produce deterministic output (no ASCII escaping)."""
    payload = {"text": "café / naïve / Δ"}
    s = canonical_json(payload)
    # ensure_ascii=False implies the literal characters are present
    assert "café" in s and "naïve" in s and "Δ" in s
    # Deterministic across calls
    assert s == canonical_json(payload)


def test_canonical_json_raises_on_non_serializable():
    """Non-serializable objects should raise (json.dumps behavior)."""
    class NotJSON:
        pass

    with pytest.raises(TypeError):
        canonical_json({"x": NotJSON()})


def test_chain_hash_first_block_matches_manual_sha256():
    """When prev_hash is None, chain_hash should hash canonical_json(payload) exactly."""
    payload = {"idx": 0, "a": 1}
    manual = hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    chained = chain_hash(None, payload)
    assert chained == manual
    assert len(chained) == 64 and all(c in string.hexdigits for c in chained)


def test_chain_hash_changes_with_prev():
    """Hash must incorporate previous hash so the chain is sensitive to history."""
    p1 = {"a": 1}
    h1 = chain_hash(None, p1)
    p2 = {"a": 2}
    h2 = chain_hash(h1, p2)
    # Same payload with different prev should produce different result
    h2_alt = chain_hash("0" * 64, p2)
    assert h1 != h2
    assert h2 != h2_alt


def test_chain_hash_tamper_propagates_downstream():
    """Changing an early payload must change all subsequent hashes (tamper-evident)."""
    p0 = {"a": 0}
    p1 = {"a": 1}
    p2 = {"a": 2}

    h0 = chain_hash(None, p0)
    h1 = chain_hash(h0, p1)
    h2 = chain_hash(h1, p2)

    # Tamper with p0 → recompute chain
    h0_t = chain_hash(None, {"a": 999})
    h1_t = chain_hash(h0_t, p1)
    h2_t = chain_hash(h1_t, p2)

    assert h0_t != h0
    assert h1_t != h1
    assert h2_t != h2  # downstream hash must change


def test_chain_hash_independent_of_key_order_in_payload():
    """Because canonical_json sorts keys, equivalent dicts produce same block hash (for same prev)."""
    prev = "ab" * 32  # 64 hex chars
    p_a = {"x": 1, "y": 2, "z": 3}
    p_b = {"z": 3, "y": 2, "x": 1}
    h_a = chain_hash(prev, p_a)
    h_b = chain_hash(prev, p_b)
    assert h_a == h_b


def test_chain_hash_randomized_sequence_is_consistent():
    """Smoke test: generate a small random chain and verify determinism across recomputation."""
    rng = random.Random(1234)
    # Build a sequence of simple payloads
    seq = [{"idx": i, "val": rng.randint(0, 100)} for i in range(10)]

    # First pass
    prev = None
    chain1 = []
    for p in seq:
        h = chain_hash(prev, p)
        chain1.append(h)
        prev = h

    # Second pass recompute; must match exactly
    prev = None
    chain2 = []
    for p in seq:
        h = chain_hash(prev, p)
        chain2.append(h)
        prev = h

    assert chain1 == chain2
