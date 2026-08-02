"""Build and load the Mojo HighwayHash shared library."""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIB = os.environ.get("MOJO_HIGHWAYHASH_LIB") or os.path.join(
    ROOT, "dist", "libmojo-highwayhash.so"
)
I = ctypes.c_int64


class BuildError(RuntimeError):
    pass


def build(force: bool = False) -> str:
    """Build the shared library if it is missing or older than its source."""
    source = os.path.join(ROOT, "src", "highwayhash.mojo")
    if not force and os.path.exists(LIB) and os.path.getmtime(LIB) >= os.path.getmtime(source):
        return LIB
    if os.environ.get("MOJO_HIGHWAYHASH_LIB"):
        raise BuildError(f"MOJO_HIGHWAYHASH_LIB does not point to a usable library: {LIB}")
    if not shutil.which("mojo"):
        raise BuildError("mojo is not on PATH; run through `pixi run` or set MOJO_HIGHWAYHASH_LIB")
    proc = subprocess.run(
        ["bash", os.path.join(ROOT, "build", "build.sh")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if proc.returncode or not os.path.exists(LIB):
        raise BuildError((proc.stderr or proc.stdout).strip()[:4000])
    return LIB


_loaded: ctypes.CDLL | None = None


def lib() -> ctypes.CDLL:
    global _loaded
    if _loaded is None:
        _loaded = ctypes.CDLL(build())
        for name in ("mhh64", "mhh128", "mhh256"):
            fn = getattr(_loaded, name)
            fn.argtypes = [I, I, I, I]
            fn.restype = None
    return _loaded
