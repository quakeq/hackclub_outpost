package com.google.mediapipe.examples.poselandmarker.streaming

import android.os.SystemClock
import android.util.Log
import com.google.mediapipe.tasks.vision.poselandmarker.PoseLandmarkerResult
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger
import java.util.concurrent.atomic.AtomicLong
import java.util.concurrent.atomic.AtomicReference

class LandmarkStreamCoordinator(
    private val settings: SensorSettings
) {

    data class Stats(
        val seq: Int,
        val sendFps: Float,
        val inferenceMs: Long,
        val drops: Int,
        val streaming: Boolean,
        val lastError: String?
    )

    interface Listener {
        fun onStats(stats: Stats)
    }

    private val udpSender = LandmarkUdpSender()
    private val wsSender = LandmarkWebSocketSender()
    private val sendExecutor: ExecutorService = Executors.newSingleThreadExecutor()

    private val seq = AtomicInteger(0)
    private val streaming = AtomicBoolean(false)
    private val sendCountWindow = AtomicInteger(0)
    private val windowStartMs = AtomicLong(SystemClock.elapsedRealtime())
    private val sendFps = AtomicReference(0f)
    private val lastError = AtomicReference<String?>(null)
    private val lastInferenceMs = AtomicLong(0)

    @Volatile
    var listener: Listener? = null

    fun start() {
        if (streaming.getAndSet(true)) return
        lastError.set(null)
        when (settings.transport) {
            Transport.UDP -> {
                udpSender.configure(settings.host, settings.udpPort)
                udpSender.open()
                wsSender.close()
            }
            Transport.WEBSOCKET -> {
                wsSender.connect(settings.host, settings.wsPort)
                udpSender.close()
            }
        }
        publishStats()
    }

    fun stop() {
        streaming.set(false)
        sendExecutor.execute {
            udpSender.close()
            wsSender.close()
        }
        publishStats()
    }

    fun isStreaming(): Boolean = streaming.get()

    fun onPoseResult(
        result: PoseLandmarkerResult,
        imageWidth: Int,
        imageHeight: Int,
        inferenceMs: Long
    ) {
        lastInferenceMs.set(inferenceMs)
        if (!streaming.get()) {
            publishStats()
            return
        }

        val hasWorld = result.worldLandmarks().isNotEmpty() &&
            result.worldLandmarks()[0].size == EXPECTED_LANDMARKS
        val hasImage = result.landmarks().isNotEmpty() &&
            result.landmarks()[0].size == EXPECTED_LANDMARKS
        if (!hasWorld && !hasImage) {
            publishStats()
            return
        }

        val nextSeq = seq.incrementAndGet()
        val packet = LandmarkMapper.fromResult(
            result = result,
            cameraId = settings.effectiveCameraId,
            seq = nextSeq,
            imageW = imageWidth,
            imageH = imageHeight
        )

        sendExecutor.execute {
            try {
                val bytes = LandmarkSerializer.encode(packet, settings.useBinary)
                when (settings.transport) {
                    Transport.UDP -> {
                        udpSender.configure(settings.host, settings.udpPort)
                        udpSender.open()
                        udpSender.send(bytes)
                    }
                    Transport.WEBSOCKET -> {
                        val ok = if (settings.useBinary) {
                            wsSender.sendBinary(bytes)
                        } else {
                            wsSender.send(bytes)
                        }
                        if (!ok) {
                            lastError.set("WebSocket not connected")
                        } else {
                            lastError.set(null)
                        }
                    }
                }
                recordSend()
                lastError.compareAndSet("UDP send failed", null)
            } catch (e: Exception) {
                lastError.set(e.message ?: "Send failed")
                Log.w(TAG, "Send error", e)
            }
            publishStats()
        }
    }

    private fun recordSend() {
        val now = SystemClock.elapsedRealtime()
        val count = sendCountWindow.incrementAndGet()
        val elapsed = now - windowStartMs.get()
        if (elapsed >= 1000L) {
            sendFps.set(count * 1000f / elapsed)
            sendCountWindow.set(0)
            windowStartMs.set(now)
        }
    }

    private fun publishStats() {
        listener?.onStats(
            Stats(
                seq = seq.get(),
                sendFps = sendFps.get(),
                inferenceMs = lastInferenceMs.get(),
                drops = udpSender.drops,
                streaming = streaming.get(),
                lastError = lastError.get()
            )
        )
    }

    fun shutdown() {
        stop()
        sendExecutor.shutdownNow()
    }

    companion object {
        private const val TAG = "LandmarkStreamCoord"
        private const val EXPECTED_LANDMARKS = 33
    }
}
