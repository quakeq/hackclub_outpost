"""16×16 addressable LED panel driver (WS2812 NeoPixel style)."""

try:
    from neopixel import NeoPixel
    from machine import Pin
except ImportError:
    NeoPixel = None
    Pin = None

try:
    from config import LED_BRIGHTNESS, LED_PIN, PANEL_H, PANEL_W
except ImportError:
    LED_PIN = 2
    LED_BRIGHTNESS = 32
    PANEL_W = 16
    PANEL_H = 16


def _serpentine_index(col, row, width=PANEL_W):
    """Map (col, row) to linear index for common serpentine matrices.

    Even rows left→right; odd rows right→left.
    """
    if row & 1:
        return row * width + (width - 1 - col)
    return row * width + col


class LedPanel:
    def __init__(
        self,
        pin=LED_PIN,
        width=PANEL_W,
        height=PANEL_H,
        brightness=LED_BRIGHTNESS,
        serpentine=True,
    ):
        self.width = width
        self.height = height
        self.n = width * height
        self.brightness = max(0, min(255, brightness))
        self.serpentine = serpentine
        self._scale = self.brightness / 255.0

        if NeoPixel is None:
            self.np = None
            self._buf = [(0, 0, 0)] * self.n
            return

        self.np = NeoPixel(Pin(pin), self.n)
        self._buf = None

    def _index(self, col, row):
        if self.serpentine:
            return _serpentine_index(col, row, self.width)
        return row * self.width + col

    def clear(self):
        if self.np is None:
            self._buf = [(0, 0, 0)] * self.n
            return
        for i in range(self.n):
            self.np[i] = (0, 0, 0)
        self.np.write()

    def show_framebuffer(self, fb):
        """Push PANEL_H × PANEL_W RGB framebuffer to the LEDs."""
        scale = self._scale
        if self.np is None:
            # Host / dry-run: keep last buffer only
            out = [(0, 0, 0)] * self.n
            for row in range(self.height):
                for col in range(self.width):
                    r, g, b = fb[row][col]
                    out[self._index(col, row)] = (
                        int(r * scale),
                        int(g * scale),
                        int(b * scale),
                    )
            self._buf = out
            return

        for row in range(self.height):
            for col in range(self.width):
                r, g, b = fb[row][col]
                self.np[self._index(col, row)] = (
                    int(r * scale),
                    int(g * scale),
                    int(b * scale),
                )
        self.np.write()
