# mojo-highwayhash

`mojo-highwayhash` is a Mojo implementation of [HighwayHash](https://github.com/google/highwayhash), the keyed SIMD hash designed for fast, short-message hashing and hash-flood resistance. Its Python wrapper deliberately mirrors the three function names and signatures exposed by the maintained `highwayhash-cffi` package:

```python
from mojohighwayhash import highwayhash_64, highwayhash_128, highwayhash_256

key = bytes(range(32))
message = b"the same key and bytes produce the upstream digest"
print(highwayhash_64(key, message).hex())
```

All functions take `(key: bytes, data: bytes) -> bytes`; `key` must be exactly 32 bytes. Outputs are 8, 16, and 32 little-endian digest bytes respectively, exactly as `highwayhash-cffi` returns them.

## Coverage

Covered completely:

- `highwayhash_64(key, data)`
- `highwayhash_128(key, data)`
- `highwayhash_256(key, data)`

This is the full public function API of `highwayhash-cffi` 0.1.6. The original C++ project also has incremental/C++ interfaces and CPU-feature dispatch; those are intentionally not exposed here. The Mojo kernel is a single-shot native x86-64 implementation and uses the frozen HighwayHash packet, remainder-padding, and finalization rules.

## Install and run

This checkout is self-contained; Pixi provides Mojo, NumPy, pytest, and the upstream reference package used by the tests.

```bash
pixi install
pixi run build
pixi run test
pixi run bench
```

For an application using this checkout, put `python/` on `PYTHONPATH`, then import `mojohighwayhash` as in the example above. The wrapper will build `dist/libmojo-highwayhash.so` on first import if it is missing or stale. Set `MOJO_HIGHWAYHASH_LIB` to use a prebuilt shared library instead.

## Benchmarks

Measured with `pixi run bench` on Linux 6.8.0-136-generic, x86_64, glibc 2.39. Times are the best of seven 8 MiB one-shot hashes; the upstream comparison is `highwayhash-cffi` 0.1.6 in the same Pixi environment.

| kernel | Mojo | upstream highwayhash-cffi | speedup |
| --- | ---: | ---: | ---: |
| `highwayhash_64` 8 MiB | 5.91 ms | 12.03 ms | 2.04x |
| `highwayhash_128` 8 MiB | 5.98 ms | 12.38 ms | 2.07x |
| `highwayhash_256` 8 MiB | 5.82 ms | 12.04 ms | 2.07x |

## How it works

The Mojo source is one compilation unit to keep build cost fixed. It keeps HighwayHash's four `UInt64` state lanes in `SIMD[DType.uint64, 4]`: full 32-byte packets are loaded as four lanes, and the add/xor/multiply state update is vectorized and inlined. The byte zipper merge and tail construction retain the reference algorithm's lane order exactly.

There is no GPU path. Each packet update depends on the prior packet's state, leaving no useful within-message parallelism, and its arithmetic intensity is too low to amortize host/device transfers. CPU SIMD is the appropriate execution path.

Python crosses the FFI boundary with four integer addresses: key bytes, message bytes, byte count, and a caller-owned `uint64` result buffer. Mojo rebuilds typed pointers internally because exported Mojo functions cannot have parametric pointer arguments. No message copy is made on the hashing path; NumPy exposes the immutable Python byte buffers directly and owns the result buffer until it is converted to `bytes`. Empty messages use a retained one-byte sentinel, so every address passed to Mojo is non-null.

## Verification

`tests/test_parity.py` compares every message length from 0 through 64, plus packet-boundary and large-message cases, against the real `highwayhash-cffi` package. It also checks Google HighwayHash's published empty-message vectors for all three output widths and confirms error types/messages match upstream.

MIT.
