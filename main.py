# Python code to read image
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# To read image from disk, we use

# Initialize Mediapipe drawing utilities and holistic model components

model_path = 'pose_landmarker_full.task'
cap = cv2.VideoCapture(0)

PoseLandmarker = mp.tasks.vision.PoseLandmarker
latest_frame=None
PoseLandmarkerResult = mp.tasks.vision.PoseLandmarkerResult                                                                                   ase_options = python.BaseOptions(model_asset_path=model_path)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.LIVE_STREAM,
    result_callback=print_result)


timestamp = 0
with PoseLandmarker.create_from_options(options) as landmarker:
    while cap.isOpened():
        ret, frame = cap.read()

        if not ret:
            print("Ignoring empty frame")
            break

        timestamp += 1

        # convert cv image to mediapipe
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame)

        # Process the frame with the holistic modelRunningModeVisionRunningMode
        landmarker.detect_async(mp_image, timestamp)

        if cv2.waitKey(5) & 0xFF == 27:
            break



cap.release()
cv2.destroyAllWindows()