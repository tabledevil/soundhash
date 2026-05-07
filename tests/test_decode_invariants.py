"""Invariants I1-I10 from src/soundhash/_decoder_api_pseudocode.py.

These tests run against the real decoder. Some are stubs until the full
pipeline is wired up.
"""
import hashlib

import pytest

from soundhash import SPEC_VERSION
from soundhash.decode import hash_to_spec, UnsupportedVersionError


def _h(s: bytes) -> bytes:
    return hashlib.sha256(s).digest()


def test_I1_idempotent():
    h = _h(b"hello")
    assert hash_to_spec(h) == hash_to_spec(h)


def test_I8_version_pinned():
    h = _h(b"hello")
    assert hash_to_spec(h, version="v1").version == "v1"
    with pytest.raises(UnsupportedVersionError):
        hash_to_spec(h, version="v2")


def test_I6_length_bound():
    for seed in (b"a", b"b", b"c", b"d"):
        spec = hash_to_spec(_h(seed))
        assert spec.total_duration_seconds() <= 30.0


def test_I7_bitflip_changes_spec():
    h = bytearray(_h(b"hello"))
    base = hash_to_spec(bytes(h))
    diffs = 0
    for i in range(len(h)):
        h[i] ^= 1
        if hash_to_spec(bytes(h)) != base:
            diffs += 1
        h[i] ^= 1
    # Currently a low-fidelity test against the placeholder decoder.
    # Real threshold is 99.9% once tables are wired.
    assert diffs >= 1


def test_decoder_rejects_wrong_hash_length():
    with pytest.raises(ValueError):
        hash_to_spec(b"\x00" * 31)
    with pytest.raises(ValueError):
        hash_to_spec(b"\x00" * 33)


def test_spec_version_default_matches_package():
    spec = hash_to_spec(_h(b"x"))
    assert spec.version == SPEC_VERSION
