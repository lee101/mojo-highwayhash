"""Drop-in function names for the `highwayhash-cffi` HighwayHash API."""

from __future__ import annotations

import numpy as np

from ._lib import lib

__version__ = "0.1.0"
__all__ = ["highwayhash_64", "highwayhash_128", "highwayhash_256"]

# NumPy permits zero-length arrays to have an implementation-defined data pointer.
# The Mojo ABI uses an address even for empty input, so keep a concrete byte alive
# and use its non-null address in that case.
_EMPTY_DATA = np.zeros(1, dtype=np.uint8)


def _process_in(key: bytes, data: bytes) -> tuple[bytes, bytes]:
    if not isinstance(key, bytes):
        raise TypeError("'key' must be of type 'bytes'")
    if not isinstance(data, bytes):
        raise TypeError("'data' must be of type 'bytes'")
    if len(key) != 32:
        raise ValueError("'key' must be of length '32'")
    return key, data


def _hash(symbol: str, key: bytes, data: bytes, words: int) -> bytes:
    key, data = _process_in(key, data)
    key_array = np.frombuffer(key, dtype=np.uint8)
    data_array = np.frombuffer(data, dtype=np.uint8)
    result = np.empty(words, dtype=np.uint64)
    data_address = data_array.ctypes.data if data_array.size else _EMPTY_DATA.ctypes.data
    # All arrays remain strongly referenced until the native call has returned.
    getattr(lib(), symbol)(key_array.ctypes.data, data_address, len(data), result.ctypes.data)
    return result.tobytes()


def highwayhash_64(key: bytes, data: bytes) -> bytes:
    """Return the 64-bit HighwayHash digest as eight little-endian bytes."""
    return _hash("mhh64", key, data, 1)


def highwayhash_128(key: bytes, data: bytes) -> bytes:
    """Return the 128-bit HighwayHash digest as sixteen little-endian bytes."""
    return _hash("mhh128", key, data, 2)


def highwayhash_256(key: bytes, data: bytes) -> bytes:
    """Return the 256-bit HighwayHash digest as thirty-two little-endian bytes."""
    return _hash("mhh256", key, data, 4)
