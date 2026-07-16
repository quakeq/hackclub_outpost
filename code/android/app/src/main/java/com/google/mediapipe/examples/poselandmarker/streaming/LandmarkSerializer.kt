package com.google.mediapipe.examples.poselandmarker.streaming

import org.json.JSONArray
import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder

object LandmarkSerializer {

    fun toJson(packet: LandmarkPacket): ByteArray {
        val landmarks = JSONArray()
        for (lm in packet.landmarks) {
            landmarks.put(
                JSONObject()
                    .put("i", lm.i)
                    .put("x", lm.x.toDouble())
                    .put("y", lm.y.toDouble())
                    .put("z", lm.z.toDouble())
                    .put("v", lm.v.toDouble())
            )
        }
        val root = JSONObject()
            .put("camera_id", packet.cameraId)
            .put("seq", packet.seq)
            .put("t_capture_ms", packet.tCaptureMs)
            .put("image_w", packet.imageW)
            .put("image_h", packet.imageH)
            .put("landmarks", landmarks)
        return root.toString().toByteArray(Charsets.UTF_8)
    }

    /**
     * Production binary layout (big-endian):
     * camera_id index (1), seq (u32), timestamp (u64), num_landmarks (u8),
     * then N × (x, y, z, visibility) float32.
     */
    fun toBinary(packet: LandmarkPacket): ByteArray {
        val count = packet.landmarks.size.coerceAtMost(255)
        val buffer = ByteBuffer.allocate(1 + 4 + 8 + 1 + count * 16)
            .order(ByteOrder.BIG_ENDIAN)
        val cameraIndex = StreamingConfig.CAMERA_ID_INDEX[packet.cameraId] ?: 0
        buffer.put(cameraIndex.toByte())
        buffer.putInt(packet.seq)
        buffer.putLong(packet.tCaptureMs)
        buffer.put(count.toByte())
        for (i in 0 until count) {
            val lm = packet.landmarks[i]
            buffer.putFloat(lm.x)
            buffer.putFloat(lm.y)
            buffer.putFloat(lm.z)
            buffer.putFloat(lm.v)
        }
        return buffer.array()
    }

    fun encode(packet: LandmarkPacket, useBinary: Boolean): ByteArray {
        return if (useBinary) toBinary(packet) else toJson(packet)
    }
}
