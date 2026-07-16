package com.google.mediapipe.examples.poselandmarker.streaming

import android.util.Log
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class LandmarkWebSocketSender {

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    @Volatile
    private var webSocket: WebSocket? = null

    private val open = AtomicBoolean(false)

    val isOpen: Boolean get() = open.get()

    fun connect(host: String, port: Int) {
        close()
        val url = "ws://$host:$port"
        val request = Request.Builder().url(url).build()
        webSocket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                open.set(true)
                Log.i(TAG, "WebSocket open: $url")
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                open.set(false)
                webSocket.close(1000, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                open.set(false)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                open.set(false)
                Log.w(TAG, "WebSocket failure: ${t.message}")
            }
        })
    }

    fun send(bytes: ByteArray): Boolean {
        val ws = webSocket ?: return false
        if (!open.get()) return false
        // JSON prototype sends text; binary mode may use bytes later
        return try {
            val text = String(bytes, Charsets.UTF_8)
            ws.send(text)
        } catch (e: Exception) {
            Log.w(TAG, "WebSocket send failed: ${e.message}")
            false
        }
    }

    fun sendBinary(bytes: ByteArray): Boolean {
        val ws = webSocket ?: return false
        if (!open.get()) return false
        return try {
            ws.send(ByteString.of(*bytes))
        } catch (e: Exception) {
            Log.w(TAG, "WebSocket binary send failed: ${e.message}")
            false
        }
    }

    fun close() {
        open.set(false)
        webSocket?.close(1000, "done")
        webSocket = null
    }

    companion object {
        private const val TAG = "LandmarkWsSender"
    }
}
