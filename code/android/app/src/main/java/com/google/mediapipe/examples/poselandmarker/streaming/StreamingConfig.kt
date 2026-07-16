package com.google.mediapipe.examples.poselandmarker.streaming

enum class Transport {
    UDP,
    WEBSOCKET
}

object StreamingConfig {
    const val DEFAULT_HOST = "192.168.50.1"
    const val DEFAULT_UDP_PORT = 9000
    const val DEFAULT_WS_PORT = 9001

    val CAMERA_ID_INDEX = mapOf(
        "phone_a" to 0,
        "phone_b" to 1,
        "phone_c" to 2
    )
}
