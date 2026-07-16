package com.google.mediapipe.examples.poselandmarker.streaming

import android.os.SystemClock
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult

object LandmarkMapper {

    fun fromResult(
        result: PoseLandmarkerResult,
        cameraId: String,
        seq: Int,
        imageW: Int,
        imageH: Int
    ): LandmarkPacket {
        val landmarks = if (result.landmarks().isEmpty()) {
            emptyList()
        } else {
            result.landmarks()[0].mapIndexed { index, landmark ->
                Landmark(
                    i = index,
                    x = landmark.x(),
                    y = landmark.y(),
                    z = landmark.z(),
                    v = landmark.visibility().orElse(0f)
                )
            }
        }
        return LandmarkPacket(
            cameraId = cameraId,
            seq = seq,
            tCaptureMs = result.timestampMs()+
                    (System.currentTimeMillis() - SystemClock.uptimeMillis()),
            imageW = imageW,
            imageH = imageH,
            landmarks = landmarks
        )
    }
}
