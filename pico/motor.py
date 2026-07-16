"""Stepper motor driver with once-per-rev index sync (MicroPython)."""

import math
import time

try:
    from machine import Pin
except ImportError:
    Pin = None

try:
    from config import (
        DIR_PIN,
        ENABLE_PIN,
        INDEX_ACTIVE_LOW,
        INDEX_PIN,
        INDEX_PULL_UP,
        STEP_INTERVAL_US,
        STEP_PIN,
        STEPS_PER_REV,
    )
except ImportError:
    STEP_PIN = 6
    DIR_PIN = 7
    ENABLE_PIN = None
    INDEX_PIN = 8
    INDEX_PULL_UP = True
    INDEX_ACTIVE_LOW = True
    STEPS_PER_REV = 3200
    STEP_INTERVAL_US = 200


class StepperMotor:
    def __init__(
        self,
        step_pin=STEP_PIN,
        dir_pin=DIR_PIN,
        enable_pin=ENABLE_PIN,
        index_pin=INDEX_PIN,
        steps_per_rev=STEPS_PER_REV,
        step_interval_us=STEP_INTERVAL_US,
    ):
        self.steps_per_rev = steps_per_rev
        self.step_interval_us = step_interval_us
        self.step_index = 0
        self.revolutions = 0
        self._last_step_us = 0
        self._index_prev = False

        if Pin is None:
            self.step = None
            self.dir = None
            self.enable = None
            self.index = None
            return

        self.step = Pin(step_pin, Pin.OUT, value=0)
        self.dir = Pin(dir_pin, Pin.OUT, value=1)
        if enable_pin is not None:
            self.enable = Pin(enable_pin, Pin.OUT, value=0)  # active low
        else:
            self.enable = None

        pull = Pin.PULL_UP if INDEX_PULL_UP else None
        self.index = Pin(index_pin, Pin.IN, pull)

    def angle(self):
        """Current motor angle in radians [0, 2π)."""
        return (self.step_index % self.steps_per_rev) * (
            2.0 * math.pi / self.steps_per_rev
        )

    def _index_active(self):
        if self.index is None:
            return False
        val = self.index.value()
        if INDEX_ACTIVE_LOW:
            return val == 0
        return val == 1

    def check_index(self):
        """Resync step counter on rising edge of index pulse."""
        active = self._index_active()
        if active and not self._index_prev:
            self.step_index = 0
            self.revolutions += 1
        self._index_prev = active

    def step_once(self):
        """Issue one microstep pulse (blocking width ~ few µs)."""
        if self.step is None:
            self.step_index = (self.step_index + 1) % self.steps_per_rev
            if self.step_index == 0:
                self.revolutions += 1
            return

        self.step.value(1)
        # Short high pulse; ~2 µs is enough for most drivers
        time.sleep_us(2)
        self.step.value(0)
        self.step_index = (self.step_index + 1) % self.steps_per_rev
        if self.step_index == 0 and not self._index_active():
            # Open-loop wrap; index will correct if present
            self.revolutions += 1

    def ready_for_step(self, now_us=None):
        if now_us is None:
            now_us = time.ticks_us()
        if time.ticks_diff(now_us, self._last_step_us) >= self.step_interval_us:
            self._last_step_us = now_us
            return True
        return False

    def update(self):
        """If enough time has elapsed, microstep once and return True."""
        now = time.ticks_us() if hasattr(time, "ticks_us") else int(time.time() * 1e6)
        self.check_index()
        if not self.ready_for_step(now):
            return False
        self.step_once()
        return True
