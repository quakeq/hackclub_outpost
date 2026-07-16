# Hack Club Outpost — Volumetric MediaPipe Pose Display

Live human pose → Wi-Fi → ESP32 → UART → Raspberry Pi Pico → rotating **16×16** addressable LED panel.

```
Webcam → PC (MediaPipe) → UDP → ESP32 → UART → Pico → stepper + LEDs
```

## Contents

| Path | Role |
|------|------|
| [`main.py`](main.py) | PC sender: webcam + PoseLandmarker → UDP |
| [`pose_protocol.py`](pose_protocol.py) | Binary frame pack/unpack + CRC-16 |
| [`esp32/pose_bridge.ino`](esp32/pose_bridge.ino) | SoftAP UDP receiver → UART forwarder |
| [`pico/`](pico/) | MicroPython firmware (motor, renderer, LEDs, UART) |

## Wire protocol

```
[0xAA][0x55]  magic
[seq: u8]
[num: u8]     always 33
[33 × (x,y,z) as big-endian int16]   scale 32767 ↔ ±1.0
[crc16: u16]  CRC-16/CCITT-FALSE over preceding bytes
```

Frame size: **204 bytes**.

## Wiring (defaults)

### ESP32 (SoftAP bridge)

- SoftAP SSID `outpost-pose` / password `outpost123`
- UDP port **5005**, AP IP **192.168.4.1**
- UART1 **921600** baud: TX pin **17**, RX pin **16** (edit defines in the sketch if needed)

### Raspberry Pi Pico

| Function | GPIO (default) |
|----------|----------------|
| UART RX (from ESP32 TX) | GP1 |
| UART TX (optional) | GP0 |
| WS2812 data | GP2 |
| Stepper STEP | GP6 |
| Stepper DIR | GP7 |
| Index / once-per-rev | GP8 (pull-up, active-low) |

Shared GND between ESP32, Pico, stepper driver, and LED panel. Use a stout 5 V supply for the 16×16 matrix; do not power the panel from the Pico 5 V pin.

Microstepping DIP switches on the driver must match [`pico/config.py`](pico/config.py) (`MICROSTEP = 16` → 3200 microsteps/rev for a 200-step motor). Supported modes: full, 1/4, 1/8, 1/16.

### Geometry

- Panel is **16×16**; the **left edge** (column 0) is hinged to the motor shaft.
- Motor angle `θ` selects which volumetric slice is drawn onto the panel.

Edit pins, RPM, brightness, and `RUN_MODE` in [`pico/config.py`](pico/config.py).

## PC setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Ensure `pose_landmarker_full.task` is present in the repo root (restored from git if deleted).

Send poses to the ESP32 AP:

```bash
python main.py --host 192.168.4.1 --port 5005
```

Optional live preview window:

```bash
python main.py --host 192.168.4.1 --debug
```

Connect your PC Wi-Fi to `outpost-pose` first (or change the sketch to station mode and point `--host` at the ESP32’s LAN IP).

## ESP32 flash

1. Open [`esp32/pose_bridge.ino`](esp32/pose_bridge.ino) in Arduino IDE / PlatformIO.
2. Select your ESP32 board and flash.
3. USB serial at 115200 prints the AP IP and forward counts.

## Pico flash (MicroPython)

1. Install MicroPython on the Pico.
2. Copy the contents of [`pico/`](pico/) to the board (Thonny, `mpremote`, etc.):

   ```bash
   mpremote cp pico/config.py pico/uart_rx.py pico/renderer.py pico/motor.py pico/leds.py pico/main.py :
   ```

3. Soft-reset; `main.py` runs automatically if named as the boot entry, or run it from the REPL.

## Bring-up sequence

Work through these stages before full-speed spinning.

### 1. Protocol only (UART debug)

On the Pico, set in `config.py`:

```python
RUN_MODE = "uart_debug"
```

Or run `main.py uart_debug`. Leave the motor and LEDs disconnected if you like.

- Flash ESP32 bridge, join `outpost-pose`, run `python main.py --host 192.168.4.1`.
- Pico USB serial should print `seq`, `nose`, `l_hip` updating when a person is visible.
- Confirm `uart_ok` climbs and `uart_bad` stays near zero.

### 2. Static T-pose (optics + motor)

```python
RUN_MODE = "static_tpose"
```

- Power the panel and stepper safely (clear surroundings).
- Start the Pico; the panel should show a skeleton cross-section that fuses into a T-pose as it spins.
- Tune `TARGET_RPM`, `SLICE_THICKNESS`, `LED_BRIGHTNESS`, and serpentine mapping in `leds.py` if the figure looks flipped or sparse.

### 3. Live pose over Wi-Fi

```python
RUN_MODE = "live"
```

- Repeat PC + ESP32 steps from stage 1.
- Walk in front of the camera; the volumetric figure should track your pose (last frame is held if detection drops).

### 4. Full stack polish

- Align the index sensor so `step_index` resets cleanly each revolution.
- Match microstep mode on the driver and in `config.py`.
- Prefer lower brightness until thermal/power headroom is clear.
- If MicroPython cannot keep up at high RPM, skip render on some microsteps or port the hot path to C/PIO.

## Safety

A spinning LED panel is a mechanical hazard. Start at low RPM, secure cables with a slip ring or careful cable management, and keep hands clear of the sweep volume.
