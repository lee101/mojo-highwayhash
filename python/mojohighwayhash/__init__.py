"""Drop-in function names for the `highwayhash-cffi` HighwayHash API."""

from __future__ import annotations

import ctypes

from ._lib import lib

__version__ = "0.1.0"
__all__ = ["highwayhash_64", "highwayhash_128", "highwayhash_256"]

_bytes_address = ctypes.pythonapi.PyBytes_AsString
_bytes_address.argtypes = [ctypes.py_object]
_bytes_address.restype = ctypes.c_void_p
_new_bytes = ctypes.pythonapi.PyBytes_FromStringAndSize
_new_bytes.argtypes = [ctypes.c_void_p, ctypes.c_ssize_t]
_new_bytes.restype = ctypes.py_object


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
    result = _new_bytes(None, words * 8)
    getattr(lib(), symbol)(
        _bytes_address(key),
        _bytes_address(data),
        len(data),
        _bytes_address(result),
    )
    return result


def highwayhash_64(key: bytes, data: bytes) -> bytes:
    """Return the 64-bit HighwayHash digest as eight little-endian bytes."""
    return _hash("mhh64", key, data, 1)


def highwayhash_128(key: bytes, data: bytes) -> bytes:
    """Return the 128-bit HighwayHash digest as sixteen little-endian bytes."""
    return _hash("mhh128", key, data, 2)


def highwayhash_256(key: bytes, data: bytes) -> bytes:
    """Return the 256-bit HighwayHash digest as thirty-two little-endian bytes."""
    return _hash("mhh256", key, data, 4)
