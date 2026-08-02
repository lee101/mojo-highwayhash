"""Measure the Mojo port against the upstream highwayhash-cffi package."""

from __future__ import annotations

import os
import platform
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"))

import highwayhash as upstream
import mojohighwayhash as mojo


def best_time(fn, repeat: int = 7) -> float:
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - start)
    return best


def main() -> None:
    key = bytes(range(32))
    data = (bytes(range(256)) * 32_768)[:8 * 1024 * 1024]
    print(f"Machine: {platform.platform()} ({platform.machine()})")
    print("| kernel | Mojo | upstream highwayhash-cffi | speedup |")
    print("| --- | ---: | ---: | ---: |")
    for name in ("highwayhash_64", "highwayhash_128", "highwayhash_256"):
        ours = getattr(mojo, name)
        theirs = getattr(upstream, name)
        ours(key, data)
        theirs(key, data)
        mojo_s = best_time(lambda: ours(key, data))
        upstream_s = best_time(lambda: theirs(key, data))
        print(f"| `{name}` 8 MiB | {mojo_s * 1e3:.2f} ms | {upstream_s * 1e3:.2f} ms | {upstream_s / mojo_s:.2f}x |")


if __name__ == "__main__":
    main()
