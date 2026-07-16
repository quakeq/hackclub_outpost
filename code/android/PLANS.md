OUTPOST PLAN — PHONES
=====================
Part of: Multi-phone MediaPipe pose → Laptop relative 2D → Rotating volumetric display

ROLE
----

Phones are sensors only. Each phone:
- Captures camera frames
- Runs MediaPipe Pose on-device
- Streams landmarks only (not video) to the laptop

Do not stream MJPEG/H.264 to the laptop and run MediaPipe there. That adds encode/decode
delay and saturates the link for no gain when phones can already run inference.


ARCHITECTURE POSITION
---------------------

Phone A ──┐
Phone B ──┼── Wi‑Fi (dedicated AP) ──► Laptop
Phone C ──┘         landmarks only


MEDIAPIPE / CAPTURE
-------------------

Prefer native MediaPipe Tasks (Android Kotlin / iOS Swift), not browser MediaPipe, if
you care about latency and frame pacing.

Pin MediaPipe to a fixed input size / FPS (e.g. 640-wide, 30 FPS) so timing is stable
across all three phones.

Per frame, send roughly:
- camera_id
- frame_id / sequence number
- t_capture (monotonic or NTP-synced time)
- 33 landmarks × (x, y, z, visibility) (and world landmarks if you use them)
- optional: image size / FOV for later calibration

Payload is typically < 2 KB/frame. At 30 FPS × 3 phones that is trivial bandwidth.


NETWORK CONNECTION
------------------

Phones join the dedicated LAN (SSID: POSE-LAN) and send UDP packets to the laptop.

| Phone   | IP               | Send to              |
|---------|------------------|----------------------|
| phone_a | 192.168.50.11    | 192.168.50.1:9000    |
| phone_b | 192.168.50.12    | 192.168.50.1:9000    |
| phone_c | 192.168.50.13    | 192.168.50.1:9000    |

Use static IPs. DHCP is fine for prototyping, but static avoids address changes breaking
your sender apps.

Protocol: UDP datagrams with seq + timestamp. Fire-and-forget — do not wait for ACK.

| Approach               | Latency | Fit                      |
|------------------------|---------|--------------------------|
| UDP + seq + timestamp  | Best    | Best for live landmarks  |
| WebSocket / TCP binary | Good    | Simplest reliable path   |
| MQTT                   | Worse   | Avoid for pose live path |
| Cloud relays           | Worst   | Avoid entirely           |

Encode with FlatBuffers or protobuf for production. JSON is fine for prototyping.


PACKET FORMAT
-------------

Prototype JSON:
{
  "camera_id": "phone_a",
  "seq": 1284,
  "t_capture_ms": 1739473821,
  "image_w": 1280,
  "image_h": 720,
  "landmarks": [
    {"i": 0, "x": 0.51, "y": 0.42, "z": -0.03, "v": 0.98}
  ]
}

Production binary:
- camera_id (1 byte)
- seq (uint32)
- timestamp (uint64)
- num_landmarks (uint8)
- 33 × (x, y, z, visibility) as float32


SENDER LOGIC
------------

Each phone app should:
1. Run MediaPipe Pose on the camera frame.
2. Grab landmarks immediately after inference.
3. Stamp t_capture_ms.
4. Increment seq.
5. Send one UDP packet to 192.168.50.1:9000.

Android/Kotlin sketch:

val json = """
{
  "camera_id":"phone_a",
  "seq":$seq,
  "t_capture_ms":$timestamp,
  "landmarks":$landmarksJson
}
""".trimIndent()

val bytes = json.toByteArray()
socket.send(DatagramPacket(bytes, bytes.size, InetAddress.getByName("192.168.50.1"), 9000))


TIME SYNC
---------

Each pose packet must include a capture timestamp.

- Sync phone clocks to laptop over SNTP if possible 
- Even if phone clocks are not perfect, relative sync within ~10–30 ms is often enough
  if the laptop buffers 1–2 frames for alignment


WI‑FI TIPS
----------

- Use 5 GHz, not 2.4 GHz
- Keep phones close to AP
- Fixed Wi‑Fi channel, not auto
- No other heavy traffic on that SSID
- Disable phone battery optimizations for your sender app
- Keep screen on / plugged in during capture
- Use identical capture resolution/FPS on all phones


PROTOTYPE PATH
--------------

1. One phone → WebSocket JSON → laptop (print FPS/latency)
2. Switch to UDP binary
3. Add second and third phones
4. Confirm 20–30 FPS stable on all three before laptop relative-2D work begins


WHAT TO AVOID
-------------

- Streaming video "just in case"
- Routing through the public internet or a phone hotspot daisy-chain
- Sending without timestamps (laptop needs them for multi-camera sync)
- Variable capture resolution/FPS across phones
