"""HighwayHash's four-lane portable core, exposed as a small C ABI."""

comptime U64x4 = SIMD[DType.uint64, 4]
comptime U8Ptr = UnsafePointer[UInt8, AnyOrigin[mut=True]]
comptime U64Ptr = UnsafePointer[UInt64, AnyOrigin[mut=True]]
comptime MASK32 = UInt64(0xFFFFFFFF)


def rotate64_by32(x: UInt64) -> UInt64:
    return (x >> 32) | (x << 32)


def zipper_merge(v1: UInt64, v0: UInt64) -> Tuple[UInt64, UInt64]:
    var a0 = ((v0 & (UInt64(0xFF) << 24)) + (v1 & (UInt64(0xFF) << 32))) >> 24
    a0 += ((v0 & (UInt64(0xFF) << 40)) + (v1 & (UInt64(0xFF) << 48))) >> 16
    a0 += v0 & (UInt64(0xFF) << 16)
    a0 += (v0 & (UInt64(0xFF) << 8)) << 32
    a0 += (v1 & (UInt64(0xFF) << 56)) >> 8
    a0 += v0 << 56
    var a1 = ((v1 & (UInt64(0xFF) << 24)) + (v0 & (UInt64(0xFF) << 32))) >> 24
    a1 += v1 & (UInt64(0xFF) << 16)
    a1 += (v1 & (UInt64(0xFF) << 40)) >> 16
    a1 += (v1 & (UInt64(0xFF) << 8)) << 24
    a1 += (v0 & (UInt64(0xFF) << 48)) >> 8
    a1 += (v1 & UInt64(0xFF)) << 48
    a1 += v0 & (UInt64(0xFF) << 56)
    return (a0, a1)


@always_inline
def update(v0: U64x4, v1: U64x4, mul0: U64x4, mul1: U64x4,
           packet: U64x4) -> Tuple[U64x4, U64x4, U64x4, U64x4]:
    var next_v0 = v0
    var next_v1 = v1 + packet + mul0
    var next_mul0 = mul0 ^ ((next_v1 & U64x4(MASK32)) * (next_v0 >> 32))
    next_v0 += mul1
    var next_mul1 = mul1 ^ ((next_v0 & U64x4(MASK32)) * (next_v1 >> 32))

    var add0, add1 = zipper_merge(next_v1[1], next_v1[0])
    next_v0[0] += add0
    next_v0[1] += add1
    add0, add1 = zipper_merge(next_v1[3], next_v1[2])
    next_v0[2] += add0
    next_v0[3] += add1
    add0, add1 = zipper_merge(next_v0[1], next_v0[0])
    next_v1[0] += add0
    next_v1[1] += add1
    add0, add1 = zipper_merge(next_v0[3], next_v0[2])
    next_v1[2] += add0
    next_v1[3] += add1
    return (next_v0, next_v1, next_mul0, next_mul1)


def initial_state(key: U64x4) -> Tuple[U64x4, U64x4, U64x4, U64x4]:
    var init0 = U64x4(0)
    init0[0] = 0xdbe6d5d5fe4cce2f
    init0[1] = 0xa4093822299f31d0
    init0[2] = 0x13198a2e03707344
    init0[3] = 0x243f6a8885a308d3
    var init1 = U64x4(0)
    init1[0] = 0x3bd39e10cb0ef593
    init1[1] = 0xc0acf169b5f18a8c
    init1[2] = 0xbe5466cf34e90c6c
    init1[3] = 0x452821e638d01377
    var rotated = U64x4(0)
    for i in range(4):
        rotated[i] = rotate64_by32(key[i])
    return (init0 ^ key, init1 ^ rotated, init0, init1)


def rotate_remainder(v: U64x4, count: Int) -> U64x4:
    var result = v
    for i in range(4):
        var lo = v[i] & MASK32
        var hi = v[i] >> 32
        lo = ((lo << UInt64(count)) | (lo >> UInt64(32 - count))) & MASK32
        hi = ((hi << UInt64(count)) | (hi >> UInt64(32 - count))) & MASK32
        result[i] = lo | (hi << 32)
    return result


def remainder_packet(bytes: U8Ptr, length: Int) -> U64x4:
    var packet = U64x4(0)
    var copied = length & ~3
    for i in range(copied):
        packet[i // 8] |= UInt64(bytes[i]) << UInt64((i & 7) * 8)
    var mod4 = length & 3
    if (length & 16) != 0:
        for i in range(4):
            packet[3] |= UInt64(bytes[length - 4 + i]) << UInt64(32 + i * 8)
    elif mod4 != 0:
        var last = UInt64(bytes[copied])
        last |= UInt64(bytes[copied + (mod4 >> 1)]) << 8
        last |= UInt64(bytes[length - 1]) << 16
        packet[2] = last
    return packet


def process(key_addr: Int, data_addr: Int, n: Int) -> Tuple[U64x4, U64x4, U64x4, U64x4]:
    var key = U64Ptr(unsafe_from_address=key_addr).load[width=4](0)
    var v0, v1, mul0, mul1 = initial_state(key)
    var offset = 0
    if n > 0:
        var words = U64Ptr(unsafe_from_address=data_addr)
        while offset <= n - 32:
            v0, v1, mul0, mul1 = update(v0, v1, mul0, mul1, words.load[width=4](offset // 8))
            offset += 32
        if offset < n:
            var rem = n - offset
            var pad = UInt64(rem) | (UInt64(rem) << 32)
            v0 += U64x4(pad)
            v1 = rotate_remainder(v1, rem)
            var bytes = U8Ptr(unsafe_from_address=data_addr + offset)
            v0, v1, mul0, mul1 = update(v0, v1, mul0, mul1, remainder_packet(bytes, rem))
    return (v0, v1, mul0, mul1)


def reduce_mod(a3_unmasked: UInt64, a2: UInt64, a1: UInt64,
               a0: UInt64) -> Tuple[UInt64, UInt64]:
    var a3 = a3_unmasked & 0x3FFFFFFFFFFFFFFF
    var a3_shl1 = (a3 << 1) | (a2 >> 63)
    var a2_shl1 = a2 << 1
    var a3_shl2 = (a3 << 2) | (a2 >> 62)
    var a2_shl2 = a2 << 2
    return (a1 ^ a3_shl1 ^ a3_shl2, a0 ^ a2_shl1 ^ a2_shl2)


@export("mhh64")
def mhh64(key: Int, data: Int, n: Int, result: Int) abi("C"):
    var v0, v1, mul0, mul1 = process(key, data, n)
    for _ in range(4):
        var packet = U64x4(0)
        packet[0] = rotate64_by32(v0[2])
        packet[1] = rotate64_by32(v0[3])
        packet[2] = rotate64_by32(v0[0])
        packet[3] = rotate64_by32(v0[1])
        v0, v1, mul0, mul1 = update(v0, v1, mul0, mul1, packet)
    U64Ptr(unsafe_from_address=result)[0] = v0[0] + v1[0] + mul0[0] + mul1[0]


@export("mhh128")
def mhh128(key: Int, data: Int, n: Int, result: Int) abi("C"):
    var v0, v1, mul0, mul1 = process(key, data, n)
    for _ in range(6):
        var packet = U64x4(0)
        packet[0] = rotate64_by32(v0[2])
        packet[1] = rotate64_by32(v0[3])
        packet[2] = rotate64_by32(v0[0])
        packet[3] = rotate64_by32(v0[1])
        v0, v1, mul0, mul1 = update(v0, v1, mul0, mul1, packet)
    var dst = U64Ptr(unsafe_from_address=result)
    dst[0] = v0[0] + mul0[0] + v1[2] + mul1[2]
    dst[1] = v0[1] + mul0[1] + v1[3] + mul1[3]


@export("mhh256")
def mhh256(key: Int, data: Int, n: Int, result: Int) abi("C"):
    var v0, v1, mul0, mul1 = process(key, data, n)
    for _ in range(10):
        var packet = U64x4(0)
        packet[0] = rotate64_by32(v0[2])
        packet[1] = rotate64_by32(v0[3])
        packet[2] = rotate64_by32(v0[0])
        packet[3] = rotate64_by32(v0[1])
        v0, v1, mul0, mul1 = update(v0, v1, mul0, mul1, packet)
    var dst = U64Ptr(unsafe_from_address=result)
    dst[1], dst[0] = reduce_mod(v1[1] + mul1[1], v1[0] + mul1[0],
                                 v0[1] + mul0[1], v0[0] + mul0[0])
    dst[3], dst[2] = reduce_mod(v1[3] + mul1[3], v1[2] + mul1[2],
                                 v0[3] + mul0[3], v0[2] + mul0[2])
