package com.google.mediapipe.examples.poselandmarker.streaming

import android.util.Log
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.util.concurrent.atomic.AtomicInteger

class LandmarkUdpSender {

    @Volatile
    private var socket: DatagramSocket? = null

    @Volatile
    private var host: String = StreamingConfig.DEFAULT_HOST

    @Volatile
    private var port: Int = StreamingConfig.DEFAULT_UDP_PORT

    private val dropCount = AtomicInteger(0)

    val drops: Int get() = dropCount.get()

    fun configure(host: String, port: Int) {
        this.host = host
        this.port = port
    }

    @Synchronized
    fun open() {
        if (socket == null || socket?.isClosed == true) {
            socket = DatagramSocket()
        }
    }

    @Synchronized
    fun close() {
        socket?.close()
        socket = null
    }

    fun send(bytes: ByteArray) {
        try {
            val sock = socket ?: return
            val address = InetAddress.getByName(host)
            sock.send(DatagramPacket(bytes, bytes.size, address, port))
        } catch (e: Exception) {
            dropCount.incrementAndGet()
            Log.w(TAG, "UDP send failed: ${e.message}")
            throw e
        }
    }

    companion object {
        private const val TAG = "LandmarkUdpSender"
    }
}
