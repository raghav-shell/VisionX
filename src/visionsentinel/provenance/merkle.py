"""RFC 6962 (Certificate Transparency) Merkle tree hashing. Standard library only.

Leaf hash = SHA-256(0x00 ‖ leaf), node hash = SHA-256(0x01 ‖ left ‖ right); for n leaves the tree splits at
the largest power of two strictly smaller than n. Leaves are ledger entry hashes (as ASCII strings).
"""

from __future__ import annotations

import hashlib


def leaf_hash(data: bytes) -> bytes:
    return hashlib.sha256(b"\x00" + data).digest()


def node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"\x01" + left + right).digest()


def _split(n: int) -> int:
    k = 1
    while k << 1 < n:
        k <<= 1
    return k


def merkle_root(leaves: list[bytes]) -> bytes:
    if not leaves:
        return hashlib.sha256(b"").digest()
    hashes = [leaf_hash(x) for x in leaves]
    return _root(hashes)


def _root(hashes: list[bytes]) -> bytes:
    if len(hashes) == 1:
        return hashes[0]
    k = _split(len(hashes))
    return node_hash(_root(hashes[:k]), _root(hashes[k:]))


def root_hex(entry_hashes: list[str]) -> str:
    return "sha256:" + merkle_root([h.encode("ascii") for h in entry_hashes]).hex()


def inclusion_proof(index: int, leaves: list[bytes]) -> list[bytes]:
    """Audit path for leaf ``index`` (RFC 6962 §2.1.1)."""
    hashes = [leaf_hash(x) for x in leaves]

    def path(m: int, d: list[bytes]) -> list[bytes]:
        if len(d) == 1:
            return []
        k = _split(len(d))
        if m < k:
            return path(m, d[:k]) + [_root(d[k:])]
        return path(m - k, d[k:]) + [_root(d[:k])]

    return path(index, hashes)


def verify_inclusion(leaf: bytes, index: int, size: int, proof: list[bytes], root: bytes) -> bool:
    """Recompute the root from a leaf and its audit path (RFC 9162 §2.1.3.2 algorithm)."""
    if index >= size:
        return False
    fn, sn = index, size - 1
    r = leaf_hash(leaf)
    for p in proof:
        if sn == 0:
            return False
        if fn % 2 == 1 or fn == sn:
            r = node_hash(p, r)
            while fn % 2 == 0 and fn != 0:
                fn >>= 1
                sn >>= 1
        else:
            r = node_hash(r, p)
        fn >>= 1
        sn >>= 1
    return sn == 0 and r == root
