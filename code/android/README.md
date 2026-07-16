# Pose Sensor (Android outpost)

Phones are **sensors only**: capture camera frames, run MediaPipe Pose on-device,
and stream landmarks (not video) to the laptop over the dedicated POSE-LAN Wi‑Fi.

See [PLANS.md](PLANS.md) for the system architecture.

## Flavors

| Flavor | `camera_id` | Application ID suffix |
|--------|-------------|------------------------|
| `phoneA` | `phone_a` | `.phone_a` |
| `phoneB` | `phone_b` | `.phone_b` |
| `phoneC` | `phone_c` | `.phone_c` |

Install one flavor per physical phone. Override `camera_id`, host, ports, and
transport (UDP / WebSocket) in the in-app Settings screen.

Default destination:

- UDP: `192.168.50.1:9000`
- WebSocket (prototype): `ws://192.168.50.1:9001`

Phone static IPs (router config, not this app): `.11` / `.12` / `.13`.

## Build

Open this directory in Android Studio, sync Gradle, then run a flavor, e.g.
`phoneADebug`, on a physical device.

```bash
./gradlew :app:assemblePhoneADebug
```

Capture is pinned to **640×480 @ 30 FPS**, lite model, GPU delegate (CPU fallback).

## Models

Models are downloaded into `app/src/main/assets` by `download_tasks.gradle`.
