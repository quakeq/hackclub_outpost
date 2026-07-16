"""PC-side sender: webcam → MediaPipe PoseLandmarker → UDP pose frames."""

from __future__ import annotations

import argparse
import socket
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_styles, drawing_utils

from pose_protocol import pack_frame

PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerResult = mp.tasks.vision.PoseLandmarkerResult

latest_frame = None
udp_sock: socket.socket | None = None
udp_addr: tuple[str, int] | None = None
frame_seq = 0
debug_preview = False
last_send_ms = 0.0
send_interval_ms = 33.0  # ~30 FPS


def draw_landmarks_on_image(rgb_image, detection_result):
    annotated_image = np.copy(rgb_image)
    pose_landmark_style = drawing_styles.get_default_pose_landmarks_style()
    pose_connection_style = drawing_utils.DrawingSpec(
        color=(0, 255, 0),
        thickness=2,
    )

    for pose_landmarks in detection_result.pose_landmarks:
        drawing_utils.draw_landmarks(
            image=annotated_image,
            landmark_list=pose_landmarks,
            connections=vision.PoseLandmarksConnections.POSE_LANDMARKS,
            landmark_drawing_spec=pose_landmark_style,
            connection_drawing_spec=pose_connection_style,
        )

    return annotated_image


def send_pose(landmarks) -> None:
    global frame_seq, last_send_ms
    if udp_sock is None or udp_addr is None:
        return

    now = time.monotonic() * 1000.0
    if now - last_send_ms < send_interval_ms:
        return
    last_send_ms = now

    packet = pack_frame(landmarks, seq=frame_seq)
    frame_seq = (frame_seq + 1) & 0xFF
    try:
        udp_sock.sendto(packet, udp_addr)
    except OSError as exc:
        print(f"UDP send failed: {exc}")


def on_result(
    result: PoseLandmarkerResult,
    output_image: mp.Image,
    timestamp_ms: int,
):
    global latest_frame

    if result.pose_landmarks:
        send_pose(result.pose_landmarks[0])

    if debug_preview:
        latest_frame = draw_landmarks_on_image(
            output_image.numpy_view(),
            result,
        ).copy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stream MediaPipe pose landmarks to ESP32 over UDP",
    )
    parser.add_argument(
        "--host",
        default="192.168.4.1",
        help="ESP32 UDP host (default: 192.168.4.1 AP mode)",
    )
    parser.add_argument("--port", type=int, default=5005, help="ESP32 UDP port")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index")
    parser.add_argument(
        "--model",
        default="pose_landmarker_full.task",
        help="Path to PoseLandmarker .task model",
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Max pose send rate",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show OpenCV window with landmark overlay",
    )
    return parser.parse_args()


def main() -> None:
    global udp_sock, udp_addr, debug_preview, send_interval_ms

    args = parse_args()
    debug_preview = args.debug
    send_interval_ms = 1000.0 / max(args.fps, 1.0)

    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_addr = (args.host, args.port)
    print(f"Sending pose frames to {args.host}:{args.port}")

    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"Could not open camera index {args.camera}")

    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(model_asset_path=args.model),
        running_mode=vision.RunningMode.LIVE_STREAM,
        result_callback=on_result,
    )

    timestamp = 0
    with PoseLandmarker.create_from_options(options) as landmarker:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Ignoring empty frame")
                break

            timestamp += 1
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            landmarker.detect_async(mp_image, timestamp)

            if debug_preview and latest_frame is not None:
                display = cv2.cvtColor(latest_frame, cv2.COLOR_RGB2BGR)
                cv2.imshow("Pose → UDP", display)
                if cv2.waitKey(5) & 0xFF == 27:
                    break
            else:
                # Keep the process responsive without a window.
                if cv2.waitKey(5) & 0xFF == 27:
                    break

    cap.release()
    if debug_preview:
        cv2.destroyAllWindows()
    if udp_sock is not None:
        udp_sock.close()


if __name__ == "__main__":
    main()
