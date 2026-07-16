"""Binary wire protocol for MediaPipe pose landmarks (PC → ESP32 → Pico).

Frame layout:
  [0xAA][0x55]           magic (2 B)
  [seq: uint8]           sequence number
  [num_landmarks: uint8] always 33
  [landmarks: 33 × 3 × int16]   x,y,z scaled (-32767..32767 ↔ -1..1)
  [crc16: uint16]        CRC-16/CCITT-FALSE over preceding bytes (big-endian)
"""

from __future__ import annotations

import struct
from typing import Iterable, Sequence

MAGIC = b"\xaa\x55"
NUM_LANDMARKS = 33
COORDS_PER_LANDMARK = 3
LANDMARK_SCALE = 32767
FRAME_HEADER_SIZE = 4  # magic + seq + num
LANDMARK_BYTES = NUM_LANDMARKS * COORDS_PER_LANDMARK * 2
CRC_SIZE = 2
FRAME_SIZE = FRAME_HEADER_SIZE + LANDMARK_BYTES + CRC_SIZE

# MediaPipe PoseLandmarksConnections.POSE_LANDMARKS (start, end) pairs.
POSE_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 7),
    (0, 4),
    (4, 5),
    (5, 6),
    (6, 8),
    (9, 10),
    (11, 12),
    (11, 13),
    (13, 15),
    (15, 17),
    (15, 19),
    (15, 21),
    (17, 19),
    (12, 14),
    (14, 16),
    (16, 18),
    (16, 20),
    (16, 22),
    (18, 20),
    (11, 23),
    (12, 24),
    (23, 24),
    (23, 25),
    (25, 27),
    (27, 29),
    (27, 31),
    (29, 31),
    (24, 26),
    (26, 28),
    (28, 30),
    (28, 32),
    (30, 32),
]


def crc16_ccitt(data: bytes | bytearray, init: int = 0xFFFF) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def _clamp_i16(value: float) -> int:
    scaled = int(round(value * LANDMARK_SCALE))
    if scaled > LANDMARK_SCALE:
        return LANDMARK_SCALE
    if scaled < -LANDMARK_SCALE:
        return -LANDMARK_SCALE
    return scaled


def pack_frame(
    landmarks: Sequence[Sequence[float]],
    seq: int = 0,
) -> bytes:
    """Pack 33 (x, y, z) landmarks into a wire frame.

    Each landmark may be a 3-tuple/list of floats in roughly [-1, 1],
    or an object with .x/.y/.z attributes (MediaPipe Landmark).
    """
    if len(landmarks) < NUM_LANDMARKS:
        raise ValueError(f"expected at least {NUM_LANDMARKS} landmarks")

    buf = bytearray(FRAME_SIZE)
    buf[0:2] = MAGIC
    buf[2] = seq & 0xFF
    buf[3] = NUM_LANDMARKS

    offset = FRAME_HEADER_SIZE
    for i in range(NUM_LANDMARKS):
        lm = landmarks[i]
        if hasattr(lm, "x"):
            x, y, z = float(lm.x), float(lm.y), float(lm.z)
        else:
            x, y, z = float(lm[0]), float(lm[1]), float(lm[2])
        struct.pack_into(
            ">hhh",
            buf,
            offset,
            _clamp_i16(x),
            _clamp_i16(y),
            _clamp_i16(z),
        )
        offset += 6

    crc = crc16_ccitt(buf[: FRAME_SIZE - CRC_SIZE])
    struct.pack_into(">H", buf, FRAME_SIZE - CRC_SIZE, crc)
    return bytes(buf)


def unpack_frame(data: bytes | bytearray) -> tuple[int, list[tuple[float, float, float]]]:
    """Validate and unpack a frame. Returns (seq, landmarks).

    Raises ValueError on magic/CRC/size errors.
    """
    if len(data) < FRAME_SIZE:
        raise ValueError(f"frame too short: {len(data)} < {FRAME_SIZE}")

    if data[0:2] != MAGIC:
        raise ValueError("bad magic")

    seq = data[2]
    num = data[3]
    if num != NUM_LANDMARKS:
        raise ValueError(f"unexpected landmark count: {num}")

    expected_crc = struct.unpack_from(">H", data, FRAME_SIZE - CRC_SIZE)[0]
    actual_crc = crc16_ccitt(data[: FRAME_SIZE - CRC_SIZE])
    if expected_crc != actual_crc:
        raise ValueError(f"crc mismatch: {expected_crc:#04x} != {actual_crc:#04x}")

    landmarks: list[tuple[float, float, float]] = []
    offset = FRAME_HEADER_SIZE
    inv = 1.0 / LANDMARK_SCALE
    for _ in range(NUM_LANDMARKS):
        x, y, z = struct.unpack_from(">hhh", data, offset)
        landmarks.append((x * inv, y * inv, z * inv))
        offset += 6

    return seq, landmarks


def landmarks_from_detection(pose_landmarks: Iterable) -> list[tuple[float, float, float]]:
    """Convert a MediaPipe NormalizedLandmarkList (or similar) to plain tuples."""
    out: list[tuple[float, float, float]] = []
    for lm in pose_landmarks:
        out.append((float(lm.x), float(lm.y), float(lm.z)))
    return out
