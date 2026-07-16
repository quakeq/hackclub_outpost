package com.google.mediapipe.examples.poselandmarker

import android.util.Size

/**
 * Shared capture / inference defaults so all phone outposts stay aligned.
 */
object CaptureConfig {
    const val INFERENCE_EVERY_N_FRAMES = 2
    val ANALYSIS_SIZE = Size(320, 240)
    const val TARGET_FPS = 15
    const val MODEL = PoseLandmarkerHelper.MODEL_POSE_LANDMARKER_FULL
    const val DELEGATE = PoseLandmarkerHelper.DELEGATE_GPU
}
