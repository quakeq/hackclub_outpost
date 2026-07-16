# Cameras!  

Phones are **sensors only**: capture camera frames, run MediaPipe Pose on-device,
and stream landmarks (not video) to the laptop over the dedicated ELLO Wi‑Fi.

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

Capture is pinned to **320×240 @ 15 FPS**, lite model, GPU delegate.

## Models

Models are downloaded into `app/src/main/assets` by `download_tasks.gradle`.
