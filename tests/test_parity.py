"""Parity with highwayhash-cffi and frozen vectors from Google HighwayHash."""

from __future__ import annotations

import ctypes

import numpy as np
import pytest

import highwayhash as upstream
import mojohighwayhash as mojo
from mojohighwayhash._lib import lib


KEY = bytes(range(32))
DATA = bytes(range(256))
FUNCTIONS = ("highwayhash_64", "highwayhash_128", "highwayhash_256")


@pytest.mark.parametrize("length", list(range(65)) + [95, 96, 97, 255])
@pytest.mark.parametrize("name", FUNCTIONS)
def test_matches_upstream_over_packet_boundaries(name, length):
    assert getattr(mojo, name)(KEY, DATA[:length]) == getattr(upstream, name)(KEY, DATA[:length])


@pytest.mark.parametrize(("name", "expected"), [
    ("highwayhash_64", "536ec222de567a90"),
    ("highwayhash_128", "c7fe8f9d8f26ed0f6f3e097f765e5633"),
    ("highwayhash_256", "f574c8c22a4844dd1f35c713730146d9ff1487b9ccbeaeb3f41d75453123da41"),
])
def test_google_published_empty_vectors(name, expected):
    assert getattr(mojo, name)(KEY, b"").hex() == expected


@pytest.mark.parametrize("name", FUNCTIONS)
def test_matches_upstream_for_large_unaligned_messages(name):
    data = (b"HighwayHash SIMD lane test\x00" * 4099) + b"tail"
    assert getattr(mojo, name)(KEY, data) == getattr(upstream, name)(KEY, data)


@pytest.mark.parametrize("bad_key", ["x" * 32, b"short", b"x" * 33])
def test_key_validation_matches_upstream(bad_key):
    with pytest.raises((TypeError, ValueError)) as ours:
        mojo.highwayhash_64(bad_key, b"data")
    with pytest.raises(type(ours.value)) as theirs:
        upstream.highwayhash_64(bad_key, b"data")
    assert str(ours.value) == str(theirs.value)


def test_data_must_be_bytes():
    with pytest.raises(TypeError, match="'data' must be of type 'bytes'"):
        mojo.highwayhash_64(KEY, bytearray(b"data"))


@pytest.mark.parametrize("name, words", [("mhh64", 1), ("mhh128", 2), ("mhh256", 4)])
def test_c_abi_handles_unaligned_read_buffers(name, words):
    """The byte-based API may give the native kernel arbitrarily aligned data."""
    key = (ctypes.c_ubyte * 33)()
    data = (ctypes.c_ubyte * 98)()
    for i, value in enumerate(KEY):
        key[i + 1] = value
    message = DATA[:97]
    for i, value in enumerate(message):
        data[i + 1] = value
    result = np.empty(words, dtype=np.uint64)
    getattr(lib(), name)(
        ctypes.addressof(key) + 1,
        ctypes.addressof(data) + 1,
        len(message),
        result.ctypes.data,
    )
    assert result.tobytes() == getattr(upstream, f"highwayhash_{words * 64}")(KEY, message)
