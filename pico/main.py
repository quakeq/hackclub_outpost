"""Raspberry Pi Pico volumetric pose display (MicroPython).

Integrates UART pose RX, stepper angle sync, slice rendering, and LED output.

Set RUN_MODE in config.py:
  live         — spin + render latest UART pose (falls back to last/T-pose)
  static_tpose — spin + render built-in T-pose (no network needed)
  uart_debug   — no motor/LEDs; print parsed landmarks over USB serial
"""

import sys
import time

from config import RUN_MODE, UART_BAUD, UART_ID, UART_RX_PIN, UART_TX_PIN
from leds import LedPanel
from motor import StepperMotor
from renderer import make_framebuffer, make_tpose_landmarks, render_slice
from uart_rx import PoseUartReceiver


def usb_print(*args):
    print(*args)


def run_uart_debug(rx):
    usb_print("uart_debug: waiting for pose frames on UART...")
    last_seq = -1
    while True:
        rx.poll()
        if rx.updated and rx.seq != last_seq:
            last_seq = rx.seq
            lm = rx.landmarks
            # Print a few landmarks for bring-up
            nose = lm[0] if lm else None
            hip = lm[23] if lm and len(lm) > 23 else None
            usb_print(
                "seq",
                rx.seq,
                "good",
                rx.good_frames,
                "bad",
                rx.bad_frames,
                "nose",
                nose,
                "l_hip",
                hip,
            )
            rx.updated = False
        time.sleep_ms(5)


def run_display(rx, use_static=False):
    motor = StepperMotor()
    panel = LedPanel()
    fb = make_framebuffer()
    pose = make_tpose_landmarks() if use_static else None
    static_pose = make_tpose_landmarks()

    usb_print(
        "display mode:",
        "static_tpose" if use_static else "live",
        "steps/rev=",
        motor.steps_per_rev,
        "step_us=",
        motor.step_interval_us,
    )

    panel.clear()
    last_report = time.ticks_ms() if hasattr(time, "ticks_ms") else 0

    while True:
        if not use_static:
            rx.poll()
            latest = rx.take_latest()
            if latest is not None:
                pose = latest

        active = pose if pose is not None else static_pose

        if motor.update():
            theta = motor.angle()
            render_slice(active, theta, fb=fb)
            panel.show_framebuffer(fb)

        # Periodic status on USB
        now = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)
        if hasattr(time, "ticks_diff"):
            due = time.ticks_diff(now, last_report) > 2000
        else:
            due = (now - last_report) > 2000
        if due:
            last_report = now
            usb_print(
                "rev",
                motor.revolutions,
                "step",
                motor.step_index,
                "uart_ok",
                rx.good_frames,
                "uart_bad",
                rx.bad_frames,
                "has_pose",
                pose is not None,
            )


def main():
    rx = PoseUartReceiver(
        uart_id=UART_ID,
        baud=UART_BAUD,
        tx_pin=UART_TX_PIN,
        rx_pin=UART_RX_PIN,
    )

    mode = RUN_MODE
    # Allow `main.py uart_debug` override from REPL args
    if len(sys.argv) > 1:
        mode = sys.argv[1]

    usb_print("hackclub_outpost pico starting, mode=", mode)

    if mode == "uart_debug":
        run_uart_debug(rx)
    elif mode == "static_tpose":
        run_display(rx, use_static=True)
    else:
        run_display(rx, use_static=False)


if __name__ == "__main__":
    main()
