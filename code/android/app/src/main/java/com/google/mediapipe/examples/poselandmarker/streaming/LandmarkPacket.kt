package com.google.mediapipe.examples.poselandmarker.streaming

data class Landmark(
    val i: Int,
    val x: Float,
    val y: Float,
    val z: Float,
    val v: Float
)

data class LandmarkPacket(
    val cameraId: String,
    val seq: Int,
    val tCaptureMs: Long,
    val imageW: Int,
    val imageH: Int,
    val landmarks: List<Landmark>
)
