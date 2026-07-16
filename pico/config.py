"""Hardware and timing configuration for the Pico volumetric display."""

# Panel
PANEL_W = 16
PANEL_H = 16

# WS2812 / NeoPixel data pin
LED_PIN = 2
LED_BRIGHTNESS = 32  # 0–255; keep modest for power/heat

# Stepper driver (STEP / DIR / optional ENABLE)
STEP_PIN = 6
DIR_PIN = 7
ENABLE_PIN = None  # set to a pin number if used; active-low assumed

# Index / once-per-rev sensor (active on rising or falling edge)
INDEX_PIN = 8
INDEX_PULL_UP = True
INDEX_ACTIVE_LOW = True

# UART from ESP32
UART_ID = 0
UART_BAUD = 921600
UART_TX_PIN = 0  # optional reply path
UART_RX_PIN = 1  # ESP32 TX → Pico RX

# Motor geometry
FULL_STEPS_PER_REV = 200
# Microstepping mode must match driver DIP switches: 1, 4, 8, or 16
MICROSTEP = 16
STEPS_PER_REV = FULL_STEPS_PER_REV * MICROSTEP  # 3200 at 1/16

# Spin rate
TARGET_RPM = 700
# Delay between microsteps in microseconds (computed from RPM)
_US_PER_REV = 60_000_000 // TARGET_RPM
STEP_INTERVAL_US = max(1, _US_PER_REV // STEPS_PER_REV)

# Rendering
SLICE_THICKNESS = 0.04  # ε in normalized volume units
VOLUME_SCALE = 0.80  # fit pose into ~80% of panel height
SKELETON_COLOR = (0, 255, 80)
JOINT_COLOR = (255, 255, 255)

# Modes: "live" | "static_tpose" | "uart_debug"
RUN_MODE = "live"
