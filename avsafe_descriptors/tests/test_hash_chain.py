
from avsafe_descriptors.integrity.hash_chain import chain_hash

def test_chain_hash_changes_with_prev():
    p1 = {"a": 1}
    h1 = chain_hash(None, p1)
    h2 = chain_hash(h1, {"a": 2})
    assert h1 != h2
