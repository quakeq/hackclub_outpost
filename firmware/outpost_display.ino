/*
 * Outpost ESP32 volumetric display
 * --------------------------------
 * Board: ESP32S3 Dev Module, USB CDC On Boot = Enabled
 * Library: FastLED
 *
 * Laptop protocol (see outpost sender.py / PLAN.md):
 *   UDP JSON to 192.168.50.20:9100 on POSE-LAN
 *
 *   {"frame_id":1842,"t_capture_ms":...,"angle":137.25,
 *    "targets":[
 *      {"part":"head","x":0.5,"y":0.2,"z":-0.1},
 *      {"part":"left_hand","x":0.2,"y":0.4,"z":0.0},
 *      {"part":"right_hand","x":0.8,"y":0.4,"z":0.0},
 *      {"part":"left_foot","x":0.4,"y":0.9,"z":0.1},
 *      {"part":"right_foot","x":0.6,"y":0.9,"z":0.1}]}
 *   {"type":"heartbeat","t_send_ms":...}
 *
 * `angle` is the current shaft angle in degrees [0, 360).
 * The five targets are the head, wrists, and ankles in MediaPipe coordinates.
 * The diameter-mounted panel paints a static cylinder plus targets intersecting
 * its current slice. Only the five targets are animated.
 *
 * Four independent 8x8 WS2812B panels arranged:
 *   [GPIO4][GPIO5]
 *   [GPIO6][GPIO7]
 *
 * Use a stout 5 V supply; common its GND with ESP32 GND. Do not power 256
 * LEDs from USB or the ESP32's 5 V pin.
 */

#include <Arduino.h>
#include <FastLED.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <math.h>
#include <string.h>
#include <stdlib.h>

// --- Wi-Fi and UDP ---
static const char *WIFI_SSID = "ELLO";
static const char *WIFI_PASS = "ellothomas995!";  // change to your AP password
static const uint8_t WIFI_IP[4] = {192, 168, 50, 20};
static const uint8_t WIFI_GW[4] = {192, 168, 50, 1};
static const uint8_t WIFI_MASK[4] = {255, 255, 255, 0};
static const uint16_t UDP_PORT = 9100;
static const uint32_t RX_TIMEOUT_MS = 1000;

// --- Four 8x8 panels forming one 16x16 display ---
#define PANEL 64
#define STRIPS 4
#define TOTAL (PANEL * STRIPS)
#define PANEL_W 16
#define PANEL_H 16
#define PANEL_PIXELS TOTAL

// Set true if the chase on each individual panel zigzags row to row.
static const bool SERPENTINE = false;
static const uint8_t LED_BRIGHTNESS = 40;
static const uint16_t LED_POWER_MA = 2000;

// Pose target mapping and rotating-slice thickness, in LED-pitch units.
static const float TARGET_X_SCALE = 10.0f;
static const float TARGET_Z_SCALE = 10.0f;
static const float TARGET_SLICE_HALF_WIDTH = 1.25f;

WiFiUDP Udp;

CRGB leds[TOTAL];
static uint8_t packetBuf[1536];
static uint8_t frameRgb[PANEL_PIXELS * 3];

struct PoseTarget {
  float x;
  float y;
  float z;
};

static const uint8_t TARGET_COUNT = 5;
static const char *TARGET_NAMES[TARGET_COUNT] = {
    "head", "left_hand", "right_hand", "left_foot", "right_foot"};
static const uint8_t TARGET_COLORS[TARGET_COUNT][3] = {
    {255, 180, 40},
    {40, 120, 255},
    {255, 60, 120},
    {40, 255, 120},
    {180, 80, 255},
};

static int32_t lastFrameId = -1;
static float currentAngle = 0.0f;
static PoseTarget currentTargets[TARGET_COUNT];
static bool havePose = false;
static uint32_t lastRxMs = 0;
static bool blanked = true;

static uint32_t okCount = 0;
static uint32_t badCount = 0;
static uint32_t dupCount = 0;

// Map (x,y) in the 16x16 square to the matching 8x8 panel.
// Physical layout: [0][1]
//                  [2][3]
static uint16_t xy(uint8_t x, uint8_t y) {
  const uint8_t panel = (y / 8) * 2 + (x / 8);
  uint8_t px = x % 8;
  const uint8_t py = y % 8;
  if (SERPENTINE && (py & 1)) {
    px = 7 - px;
  }
  return panel * PANEL + py * 8 + px;
}

static void led_driver_clear() {
  FastLED.clear(true);
}

static void led_driver_show_rgb888(const uint8_t *rgb888) {
  for (uint8_t y = 0; y < PANEL_H; y++) {
    for (uint8_t x = 0; x < PANEL_W; x++) {
      const size_t off = ((size_t)y * PANEL_W + x) * 3;
      leds[xy(x, y)] =
          CRGB(rgb888[off], rgb888[off + 1], rgb888[off + 2]);
    }
  }
  FastLED.show();
}

static void led_driver_begin() {
  FastLED.addLeds<WS2812B, 6, GRB>(leds, 0 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 5, GRB>(leds, 1 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 4, GRB>(leds, 2 * PANEL, PANEL);
  FastLED.addLeds<WS2812B, 7, GRB>(leds, 3 * PANEL, PANEL);
  FastLED.setMaxPowerInVoltsAndMilliamps(5, LED_POWER_MA);
  FastLED.setBrightness(LED_BRIGHTNESS);
  led_driver_clear();
}

// --- tiny JSON number extractors (no ArduinoJson dependency) ---

static const char *find_key(const char *json, const char *key) {
  // Match "key" then optional whitespace and ':'.
  char pattern[48];
  const size_t keyLen = strlen(key);
  if (keyLen + 3 >= sizeof(pattern)) {
    return nullptr;
  }
  pattern[0] = '"';
  memcpy(pattern + 1, key, keyLen);
  pattern[keyLen + 1] = '"';
  pattern[keyLen + 2] = '\0';

  const char *p = json;
  while ((p = strstr(p, pattern)) != nullptr) {
    const char *after = p + keyLen + 2;
    while (*after == ' ' || *after == '\t') {
      after++;
    }
    if (*after != ':') {
      p += keyLen + 2;
      continue;
    }
    return after + 1;
  }
  return nullptr;
}

static bool parse_number_after(const char *valueStart, double *out) {
  if (valueStart == nullptr || out == nullptr) {
    return false;
  }
  while (*valueStart == ' ' || *valueStart == '\t') {
    valueStart++;
  }
  char *end = nullptr;
  const double v = strtod(valueStart, &end);
  if (end == valueStart) {
    return false;
  }
  *out = v;
  return true;
}

static bool json_get_number(const char *json, const char *key, double *out) {
  return parse_number_after(find_key(json, key), out);
}

static bool json_is_heartbeat(const char *json) {
  const char *type = strstr(json, "\"type\"");
  if (type == nullptr) {
    return false;
  }
  return strstr(type, "heartbeat") != nullptr;
}

static bool json_get_target(const char *json, const char *part, PoseTarget *out) {
  if (out == nullptr) {
    return false;
  }
  const char *partAt = strstr(json, part);
  if (partAt == nullptr) {
    return false;
  }
  double x = 0;
  double y = 0;
  double z = 0;
  if (!json_get_number(partAt, "x", &x) ||
      !json_get_number(partAt, "y", &y) ||
      !json_get_number(partAt, "z", &z) ||
      !isfinite(x) || !isfinite(y) || !isfinite(z)) {
    return false;
  }
  out->x = (float)x;
  out->y = (float)y;
  out->z = (float)z;
  return true;
}

static float wrap360(float deg) {
  while (deg < 0.0f) {
    deg += 360.0f;
  }
  while (deg >= 360.0f) {
    deg -= 360.0f;
  }
  return deg;
}

static void set_pixel(uint8_t col, uint8_t row, uint8_t r, uint8_t g, uint8_t b) {
  const size_t off = ((size_t)row * PANEL_W + col) * 3;
  frameRgb[off] = r;
  frameRgb[off + 1] = g;
  frameRgb[off + 2] = b;
}

static void add_pixel(uint8_t col, uint8_t row, uint8_t r, uint8_t g, uint8_t b) {
  const size_t off = ((size_t)row * PANEL_W + col) * 3;
  const uint16_t nr = (uint16_t)frameRgb[off] + r;
  const uint16_t ng = (uint16_t)frameRgb[off + 1] + g;
  const uint16_t nb = (uint16_t)frameRgb[off + 2] + b;
  frameRgb[off] = nr > 255 ? 255 : (uint8_t)nr;
  frameRgb[off + 1] = ng > 255 ? 255 : (uint8_t)ng;
  frameRgb[off + 2] = nb > 255 ? 255 : (uint8_t)nb;
}

static float clampf(float value, float low, float high) {
  return value < low ? low : (value > high ? high : value);
}

static void draw_target(int col, int row, const uint8_t color[3]) {
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      const int c = col + dx;
      const int r = row + dy;
      if (c < 0 || c >= PANEL_W || r < 0 || r >= PANEL_H) {
        continue;
      }
      const uint8_t scale = (dx == 0 && dy == 0) ? 255 : 80;
      add_pixel(
          (uint8_t)c,
          (uint8_t)r,
          (uint8_t)(((uint16_t)color[0] * scale) / 255),
          (uint8_t)(((uint16_t)color[1] * scale) / 255),
          (uint8_t)(((uint16_t)color[2] * scale) / 255));
    }
  }
}

// Plot a single pixel with bounds checking.
static void plot(int col, int row, const uint8_t c[3]) {
  if (col < 0 || col >= PANEL_W || row < 0 || row >= PANEL_H) {
    return;
  }
  set_pixel((uint8_t)col, (uint8_t)row, c[0], c[1], c[2]);
}

// Bresenham line drawing; produces a 1-pixel wide line on the 16x16 grid.
static void draw_line(int x0, int y0, int x1, int y1, const uint8_t c[3]) {
  int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
  int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;

  for (;;) {
    plot(x0, y0, c);
    if (x0 == x1 && y0 == y1) {
      break;
    }
    const int e2 = 2 * err;
    if (e2 >= dy) {
      err += dy;
      x0 += sx;
    }
    if (e2 <= dx) {
      err += dx;
      y0 += sy;
    }
  }
}

// Draw a radius-1 ring: the 8 neighbors around (cx, cy).
static void draw_ring1(int cx, int cy, const uint8_t c[3]) {
  plot(cx - 1, cy - 1, c);
  plot(cx, cy - 1, c);
  plot(cx + 1, cy - 1, c);
  plot(cx - 1, cy, c);
  plot(cx + 1, cy, c);
  plot(cx - 1, cy + 1, c);
  plot(cx, cy + 1, c);
  plot(cx + 1, cy + 1, c);
}

static void render_slice(float angle_deg, const PoseTarget targets[TARGET_COUNT]) {
  (void)angle_deg;  // This sketch draws the figure flat from x/y.
  memset(frameRgb, 0, sizeof(frameRgb));

  // Warm amber stick-figure color.
  const uint8_t c[3] = {255, 180, 40};

  // Project targets flat: col = x*(PANEL_W-1), row = y*(PANEL_H-1).
  const int headCol = (int)lroundf(clampf(targets[0].x, 0.0f, 1.0f) *
                                   (float)(PANEL_W - 1));
  const int headRow = (int)lroundf(clampf(targets[0].y, 0.0f, 1.0f) *
                                   (float)(PANEL_H - 1));

  const int leftHandCol =
      (int)lroundf(clampf(targets[1].x, 0.0f, 1.0f) * (float)(PANEL_W - 1));
  const int leftHandRow =
      (int)lroundf(clampf(targets[1].y, 0.0f, 1.0f) * (float)(PANEL_H - 1));

  const int rightHandCol =
      (int)lroundf(clampf(targets[2].x, 0.0f, 1.0f) * (float)(PANEL_W - 1));
  const int rightHandRow =
      (int)lroundf(clampf(targets[2].y, 0.0f, 1.0f) * (float)(PANEL_H - 1));

  const int leftFootCol =
      (int)lroundf(clampf(targets[3].x, 0.0f, 1.0f) * (float)(PANEL_W - 1));
  const int leftFootRow =
      (int)lroundf(clampf(targets[3].y, 0.0f, 1.0f) * (float)(PANEL_H - 1));

  const int rightFootCol =
      (int)lroundf(clampf(targets[4].x, 0.0f, 1.0f) * (float)(PANEL_W - 1));
  const int rightFootRow =
      (int)lroundf(clampf(targets[4].y, 0.0f, 1.0f) * (float)(PANEL_H - 1));

  // Waist is always 40% of the screen below the head.
  const int waistDelta = (int)lroundf(0.40f * (float)PANEL_H);
  int waistRow = headRow + waistDelta;
  if (waistRow < 0) {
    waistRow = 0;
  }
  if (waistRow >= PANEL_H) {
    waistRow = PANEL_H - 1;
  }
  const int waistCol = headCol;

  // Arms start 1 LED below the head.
  int shoulderRow = headRow + 1;
  if (shoulderRow < 0) {
    shoulderRow = 0;
  }
  if (shoulderRow >= PANEL_H) {
    shoulderRow = PANEL_H - 1;
  }
  const int shoulderCol = headCol;

  draw_ring1(headCol, headRow, c);

  // Spine.
  draw_line(headCol, headRow, waistCol, waistRow, c);

  // Legs.
  draw_line(waistCol, waistRow, leftFootCol, leftFootRow, c);
  draw_line(waistCol, waistRow, rightFootCol, rightFootRow, c);

  // Arms.
  draw_line(shoulderCol, shoulderRow, leftHandCol, leftHandRow, c);
  draw_line(shoulderCol, shoulderRow, rightHandCol, rightHandRow, c);
}

static void show_idle() {
  memset(frameRgb, 0, sizeof(frameRgb));
  // Dim chasing dot so a live but unfed board is obvious.
  const uint8_t col = (millis() / 80) % PANEL_W;
  const uint8_t row = PANEL_H / 2;
  set_pixel(col, row, 0, 0, 40);
  led_driver_show_rgb888(frameRgb);
}

static void apply_display() {
  render_slice(currentAngle, currentTargets);
  led_driver_show_rgb888(frameRgb);
  blanked = false;
}

static bool handle_json(const char *json) {
  if (json_is_heartbeat(json)) {
    lastRxMs = millis();
    return true;
  }

  double frameId = 0;
  double angle = 0;
  if (!json_get_number(json, "frame_id", &frameId) ||
      !json_get_number(json, "angle", &angle) ||
      !isfinite(frameId) || !isfinite(angle)) {
    return false;
  }

  PoseTarget parsedTargets[TARGET_COUNT];
  for (uint8_t i = 0; i < TARGET_COUNT; i++) {
    if (!json_get_target(json, TARGET_NAMES[i], &parsedTargets[i])) {
      return false;
    }
  }

  const int32_t id = (int32_t)frameId;
  if (id <= lastFrameId) {
    dupCount++;
    lastRxMs = millis();
    return true;  // well-formed but stale/duplicate
  }

  lastFrameId = id;
  currentAngle = wrap360((float)angle);
  memcpy(currentTargets, parsedTargets, sizeof(currentTargets));
  havePose = true;
  lastRxMs = millis();
  apply_display();
  return true;
}

static void connect_wifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);

  IPAddress ip(WIFI_IP[0], WIFI_IP[1], WIFI_IP[2], WIFI_IP[3]);
  IPAddress gw(WIFI_GW[0], WIFI_GW[1], WIFI_GW[2], WIFI_GW[3]);
  IPAddress mask(WIFI_MASK[0], WIFI_MASK[1], WIFI_MASK[2], WIFI_MASK[3]);
  if (!WiFi.config(ip, gw, mask)) {
    Serial.println("WiFi.config failed");
  }

  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASS);

  const uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && (millis() - start) < 20000) {
    delay(250);
    Serial.print('.');
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("IP ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi connect timed out — will keep retrying");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  led_driver_begin();
  show_idle();

  connect_wifi();

  Udp.begin(UDP_PORT);
  Serial.print("UDP listen :");
  Serial.println(UDP_PORT);
  Serial.println("outpost_display ready (angle + 5 targets JSON)");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    static uint32_t lastAttempt = 0;
    if (millis() - lastAttempt > 3000) {
      lastAttempt = millis();
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_PASS);
      Serial.println("WiFi reconnecting...");
    }
  }

  const int packetSize = Udp.parsePacket();
  if (packetSize > 0) {
    if (packetSize >= (int)sizeof(packetBuf)) {
      while (Udp.available()) {
        Udp.read();
      }
      badCount++;
    } else {
      const int len = Udp.read(packetBuf, packetSize);
      if (len > 0) {
        packetBuf[len] = 0;
        if (handle_json((const char *)packetBuf)) {
          okCount++;
        } else {
          badCount++;
        }
        if ((okCount & 0x3F) == 0) {
          Serial.print("ok=");
          Serial.print(okCount);
          Serial.print(" bad=");
          Serial.print(badCount);
          Serial.print(" dup=");
          Serial.print(dupCount);
          Serial.print(" angle=");
          Serial.println(currentAngle, 1);
        }
      }
    }
  }

  const uint32_t now = millis();
  if (havePose && !blanked && (now - lastRxMs) > RX_TIMEOUT_MS) {
    led_driver_clear();
    blanked = true;
    havePose = false;
    Serial.println("rx timeout — blanked");
  }

  if (!havePose) {
    static uint32_t lastIdle = 0;
    if (now - lastIdle > 80) {
      lastIdle = now;
      show_idle();
    }
  }
}
