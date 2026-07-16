/*
 * ESP32 pose bridge: Wi-Fi UDP → UART forwarder for Raspberry Pi Pico.
 *
 * SoftAP defaults (change WIFI_SSID / WIFI_PASS as needed):
 *   SSID: outpost-pose
 *   Password: outpost123
 *   AP IP: 192.168.4.1
 *   UDP port: 5005
 *
 * UART to Pico (Serial1):
 *   Baud: 921600
 *   ESP32 TX → Pico RX
 *   ESP32 RX ← Pico TX (optional)
 *   Common GND
 */

#include <WiFi.h>
#include <WiFiUdp.h>

// ---- CONFIG ----
static const char *WIFI_SSID = "outpost-pose";
static const char *WIFI_PASS = "outpost123";
static const uint16_t UDP_PORT = 5005;

// Hardware Serial1 pins (adjust for your board):
//   ESP32 classic DevKit: TX=17, RX=16
//   ESP32-S3: often TX=17, RX=18 — change if needed
#ifndef UART_TX_PIN
#define UART_TX_PIN 17
#endif
#ifndef UART_RX_PIN
#define UART_RX_PIN 16
#endif

static const uint32_t UART_BAUD = 921600;
static const size_t MAX_PACKET = 512;

WiFiUDP Udp;
uint8_t packetBuf[MAX_PACKET];
uint32_t packetCount = 0;

void setup() {
  Serial.begin(115200);
  delay(200);

  // Pico link
  Serial1.begin(UART_BAUD, SERIAL_8N1, UART_RX_PIN, UART_TX_PIN);

  WiFi.mode(WIFI_AP);
  bool ok = WiFi.softAP(WIFI_SSID, WIFI_PASS);
  if (!ok) {
    Serial.println("softAP failed");
  }

  IPAddress ip = WiFi.softAPIP();
  Serial.print("AP IP: ");
  Serial.println(ip);

  Udp.begin(UDP_PORT);
  Serial.print("Listening UDP port ");
  Serial.println(UDP_PORT);
  Serial.print("UART baud ");
  Serial.println(UART_BAUD);
}

void loop() {
  int packetSize = Udp.parsePacket();
  if (packetSize <= 0) {
    return;
  }

  if (packetSize > (int)MAX_PACKET) {
    // Drain oversized packet.
    while (Udp.available()) {
      Udp.read();
    }
    return;
  }

  int len = Udp.read(packetBuf, packetSize);
  if (len <= 0) {
    return;
  }

  size_t written = Serial1.write(packetBuf, (size_t)len);
  Serial1.flush();

  packetCount++;
  if ((packetCount & 0x1F) == 0) {
    Serial.print("fwd ");
    Serial.print(packetCount);
    Serial.print(" last=");
    Serial.print(len);
    Serial.print(" wrote=");
    Serial.println(written);
  }
}
