"""UART pose frame parser for MicroPython on Raspberry Pi Pico."""

import struct

try:
    from machine import UART, Pin
except ImportError:  # CPython unit-test / host scrape
    UART = None
    Pin = None

MAGIC0 = 0xAA
MAGIC1 = 0x55
NUM_LANDMARKS = 33
LANDMARK_SCALE = 32767
FRAME_HEADER_SIZE = 4
LANDMARK_BYTES = NUM_LANDMARKS * 3 * 2
CRC_SIZE = 2
FRAME_SIZE = FRAME_HEADER_SIZE + LANDMARK_BYTES + CRC_SIZE


def crc16_ccitt(data, init=0xFFFF):
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def unpack_frame(data):
    """Return (seq, landmarks) or raise ValueError."""
    if len(data) < FRAME_SIZE:
        raise ValueError("short")
    if data[0] != MAGIC0 or data[1] != MAGIC1:
        raise ValueError("magic")
    seq = data[2]
    num = data[3]
    if num != NUM_LANDMARKS:
        raise ValueError("count")
    expected = struct.unpack_from(">H", data, FRAME_SIZE - CRC_SIZE)[0]
    actual = crc16_ccitt(data[: FRAME_SIZE - CRC_SIZE])
    if expected != actual:
        raise ValueError("crc")
    inv = 1.0 / LANDMARK_SCALE
    landmarks = []
    offset = FRAME_HEADER_SIZE
    for _ in range(NUM_LANDMARKS):
        x, y, z = struct.unpack_from(">hhh", data, offset)
        landmarks.append((x * inv, y * inv, z * inv))
        offset += 6
    return seq, landmarks


class PoseUartReceiver:
    """Incremental UART reader that keeps only the latest valid pose."""

    def __init__(self, uart_id=0, baud=921600, tx_pin=0, rx_pin=1):
        self._buf = bytearray()
        self.seq = -1
        self.landmarks = None
        self.updated = False
        self.good_frames = 0
        self.bad_frames = 0
        if UART is None:
            self.uart = None
            return
        self.uart = UART(
            uart_id,
            baudrate=baud,
            tx=Pin(tx_pin),
            rx=Pin(rx_pin),
            timeout=0,
        )

    def feed(self, data):
        """Push bytes (for tests or alternate sources)."""
        self._buf.extend(data)
        self._parse()

    def poll(self):
        """Read available UART bytes and parse complete frames."""
        if self.uart is None:
            return
        n = self.uart.any()
        if n:
            self._buf.extend(self.uart.read(n))
            self._parse()

    def take_latest(self):
        """Return landmarks if a new frame arrived since last take, else None."""
        if not self.updated or self.landmarks is None:
            return None
        self.updated = False
        return self.landmarks

    def _parse(self):
        # Seek magic, then attempt full frames.
        while True:
            # Need at least magic
            while len(self._buf) >= 2:
                if self._buf[0] == MAGIC0 and self._buf[1] == MAGIC1:
                    break
                # Drop leading junk
                del self._buf[0]
            else:
                return

            if len(self._buf) < FRAME_SIZE:
                return

            frame = self._buf[:FRAME_SIZE]
            try:
                seq, landmarks = unpack_frame(frame)
            except ValueError:
                self.bad_frames += 1
                # Resync: drop first magic byte and continue
                del self._buf[0]
                continue

            del self._buf[:FRAME_SIZE]
            self.seq = seq
            self.landmarks = landmarks
            self.updated = True
            self.good_frames += 1
