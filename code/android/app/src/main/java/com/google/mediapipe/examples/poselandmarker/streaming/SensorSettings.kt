package com.google.mediapipe.examples.poselandmarker.streaming

import android.content.Context
import com.google.mediapipe.examples.poselandmarker.BuildConfig

class SensorSettings(context: Context) {

    private val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    var cameraIdOverride: String?
        get() = prefs.getString(KEY_CAMERA_ID_OVERRIDE, null)?.takeIf { it.isNotBlank() }
        set(value) {
            prefs.edit().apply {
                if (value.isNullOrBlank()) remove(KEY_CAMERA_ID_OVERRIDE)
                else putString(KEY_CAMERA_ID_OVERRIDE, value)
            }.apply()
        }

    val effectiveCameraId: String
        get() = cameraIdOverride ?: BuildConfig.CAMERA_ID

    var host: String
        get() = prefs.getString(KEY_HOST, StreamingConfig.DEFAULT_HOST)
            ?: StreamingConfig.DEFAULT_HOST
        set(value) = prefs.edit().putString(KEY_HOST, value).apply()

    var udpPort: Int
        get() = prefs.getInt(KEY_UDP_PORT, StreamingConfig.DEFAULT_UDP_PORT)
        set(value) = prefs.edit().putInt(KEY_UDP_PORT, value).apply()

    var wsPort: Int
        get() = prefs.getInt(KEY_WS_PORT, StreamingConfig.DEFAULT_WS_PORT)
        set(value) = prefs.edit().putInt(KEY_WS_PORT, value).apply()

    var transport: Transport
        get() = try {
            Transport.valueOf(
                prefs.getString(KEY_TRANSPORT, Transport.UDP.name) ?: Transport.UDP.name
            )
        } catch (_: IllegalArgumentException) {
            Transport.UDP
        }
        set(value) = prefs.edit().putString(KEY_TRANSPORT, value.name).apply()

    var useBinary: Boolean
        get() = prefs.getBoolean(KEY_USE_BINARY, false)
        set(value) = prefs.edit().putBoolean(KEY_USE_BINARY, value).apply()

    var batteryOptPrompted: Boolean
        get() = prefs.getBoolean(KEY_BATTERY_OPT_PROMPTED, false)
        set(value) = prefs.edit().putBoolean(KEY_BATTERY_OPT_PROMPTED, value).apply()

    fun destinationLabel(): String {
        return when (transport) {
            Transport.UDP -> "udp://${host}:${udpPort}"
            Transport.WEBSOCKET -> "ws://${host}:${wsPort}"
        }
    }

    companion object {
        private const val PREFS_NAME = "pose_sensor_settings"
        private const val KEY_CAMERA_ID_OVERRIDE = "camera_id_override"
        private const val KEY_HOST = "host"
        private const val KEY_UDP_PORT = "udp_port"
        private const val KEY_WS_PORT = "ws_port"
        private const val KEY_TRANSPORT = "transport"
        private const val KEY_USE_BINARY = "use_binary"
        private const val KEY_BATTERY_OPT_PROMPTED = "battery_opt_prompted"
    }
}
