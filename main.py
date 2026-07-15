import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.vision import drawing_styles, drawing_utils


model_path = 'pose_landmarker_full.task'
cap = cv2.VideoCapture(0)

PoseLandmarker = mp.tasks.vision.PoseLandmarker
PoseLandmarkerResult = mp.tasks.vision.PoseLandmarkerResult

latest_frame = None


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


def print_result(
    result: PoseLandmarkerResult,
    output_image: mp.Image,
    timestamp_ms: int,
):
    global latest_frame
    latest_frame = draw_landmarks_on_image(
        output_image.numpy_view(),
        result,
    ).copy()


base_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    result_callback=print_result,
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

        if latest_frame is not None:
            display = cv2.cvtColor(latest_frame, cv2.COLOR_RGB2BGR)
            cv2.imshow('Show', display)

        if cv2.waitKey(5) & 0xFF == 27:
            break


cap.release()
cv2.destroyAllWindows()