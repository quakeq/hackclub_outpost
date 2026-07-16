package com.google.mediapipe.examples.poselandmarker.fragment

import android.annotation.SuppressLint
import android.content.Intent
import android.content.res.Configuration
import android.hardware.camera2.CaptureRequest
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.util.Log
import android.util.Range
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ArrayAdapter
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.core.Camera
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.navigation.Navigation
import com.google.mediapipe.examples.poselandmarker.CaptureConfig
import com.google.mediapipe.examples.poselandmarker.MainViewModel
import com.google.mediapipe.examples.poselandmarker.PoseLandmarkerHelper
import com.google.mediapipe.examples.poselandmarker.R
import com.google.mediapipe.examples.poselandmarker.databinding.DialogSensorSettingsBinding
import com.google.mediapipe.examples.poselandmarker.databinding.FragmentCameraBinding
import com.google.mediapipe.examples.poselandmarker.service.PoseStreamService
import com.google.mediapipe.examples.poselandmarker.streaming.LandmarkStreamCoordinator
import com.google.mediapipe.examples.poselandmarker.streaming.SensorSettings
import com.google.mediapipe.examples.poselandmarker.streaming.Transport
import com.google.mediapipe.tasks.vision.core.RunningMode
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class CameraFragment : Fragment(), PoseLandmarkerHelper.LandmarkerListener {

    companion object {
        private const val TAG = "PoseSensor"
    }

    private var _fragmentCameraBinding: FragmentCameraBinding? = null
    private val fragmentCameraBinding get() = _fragmentCameraBinding!!

    private lateinit var poseLandmarkerHelper: PoseLandmarkerHelper
    private lateinit var sensorSettings: SensorSettings
    private lateinit var streamCoordinator: LandmarkStreamCoordinator
    private val viewModel: MainViewModel by activityViewModels()

    private var preview: Preview? = null
    private var imageAnalyzer: ImageAnalysis? = null
    private var camera: Camera? = null
    private var cameraProvider: ProcessCameraProvider? = null

    private lateinit var backgroundExecutor: ExecutorService

    override fun onResume() {
        super.onResume()
        if (!PermissionsFragment.hasPermissions(requireContext())) {
            Navigation.findNavController(
                requireActivity(), R.id.fragment_container
            ).navigate(R.id.action_camera_to_permissions)
            return
        }

        backgroundExecutor.execute {
            if (this::poseLandmarkerHelper.isInitialized) {
                if (poseLandmarkerHelper.isClose()) {
                    poseLandmarkerHelper.setupPoseLandmarker()
                }
            }
        }

        if (viewModel.streamingEnabled && this::streamCoordinator.isInitialized) {
            startStreaming()
        }
        refreshStatusLabels()
    }

    override fun onPause() {
        super.onPause()
        if (this::poseLandmarkerHelper.isInitialized) {
            backgroundExecutor.execute { poseLandmarkerHelper.clearPoseLandmarker() }
        }
        if (this::streamCoordinator.isInitialized) {
            streamCoordinator.stop()
        }
        PoseStreamService.stop(requireContext())
    }

    override fun onDestroyView() {
        _fragmentCameraBinding = null
        if (this::streamCoordinator.isInitialized) {
            streamCoordinator.shutdown()
        }
        super.onDestroyView()
        backgroundExecutor.shutdown()
        backgroundExecutor.awaitTermination(Long.MAX_VALUE, TimeUnit.NANOSECONDS)
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _fragmentCameraBinding =
            FragmentCameraBinding.inflate(inflater, container, false)
        return fragmentCameraBinding.root
    }

    @SuppressLint("MissingPermission")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        sensorSettings = SensorSettings(requireContext())
        streamCoordinator = LandmarkStreamCoordinator(sensorSettings)
        streamCoordinator.listener = object : LandmarkStreamCoordinator.Listener {
            override fun onStats(stats: LandmarkStreamCoordinator.Stats) {
                activity?.runOnUiThread {
                    if (_fragmentCameraBinding == null) return@runOnUiThread
                    fragmentCameraBinding.statusMetrics.text = getString(
                        R.string.status_metrics,
                        stats.seq,
                        stats.sendFps,
                        stats.inferenceMs
                    )
                    if (stats.lastError.isNullOrBlank()) {
                        fragmentCameraBinding.statusError.visibility = View.GONE
                    } else {
                        fragmentCameraBinding.statusError.visibility = View.VISIBLE
                        fragmentCameraBinding.statusError.text = stats.lastError
                    }
                    updateStreamingButton()
                }
            }
        }

        backgroundExecutor = Executors.newSingleThreadExecutor()

        fragmentCameraBinding.viewFinder.post {
            setUpCamera()
        }

        backgroundExecutor.execute {
            poseLandmarkerHelper = PoseLandmarkerHelper(
                context = requireContext(),
                runningMode = RunningMode.LIVE_STREAM,
                currentModel = CaptureConfig.MODEL,
                currentDelegate = CaptureConfig.DELEGATE,
                poseLandmarkerHelperListener = this
            )
        }

        fragmentCameraBinding.btnSettings.setOnClickListener { showSettingsDialog() }
        fragmentCameraBinding.btnToggleStream.setOnClickListener {
            if (streamCoordinator.isStreaming()) {
                viewModel.streamingEnabled = false
                stopStreaming()
            } else {
                viewModel.streamingEnabled = true
                startStreaming()
            }
            refreshStatusLabels()
        }

        maybePromptBatteryOptimization()
        if (viewModel.streamingEnabled) {
            startStreaming()
        }
        refreshStatusLabels()
    }

    private fun startStreaming() {
        streamCoordinator.start()
        PoseStreamService.start(requireContext())
        updateStreamingButton()
        refreshStatusLabels()
    }

    private fun stopStreaming() {
        streamCoordinator.stop()
        PoseStreamService.stop(requireContext())
        updateStreamingButton()
        refreshStatusLabels()
    }

    private fun updateStreamingButton() {
        fragmentCameraBinding.btnToggleStream.setText(
            if (streamCoordinator.isStreaming()) R.string.btn_stop_streaming
            else R.string.btn_start_streaming
        )
        fragmentCameraBinding.statusStreaming.setText(
            if (streamCoordinator.isStreaming()) R.string.status_streaming_on
            else R.string.status_streaming_off
        )
    }

    private fun refreshStatusLabels() {
        if (_fragmentCameraBinding == null) return
        fragmentCameraBinding.statusCameraId.text =
            getString(R.string.status_camera_id, sensorSettings.effectiveCameraId)
        fragmentCameraBinding.statusDestination.text =
            getString(R.string.status_destination, sensorSettings.destinationLabel())
        updateStreamingButton()
    }

    private fun showSettingsDialog() {
        val dialogBinding = DialogSensorSettingsBinding.inflate(layoutInflater)
        val cameraIds = resources.getStringArray(R.array.camera_id_options)
        val transports = resources.getStringArray(R.array.transport_options)

        dialogBinding.spinnerCameraId.adapter = ArrayAdapter(
            requireContext(),
            android.R.layout.simple_spinner_dropdown_item,
            cameraIds
        )
        val currentId = sensorSettings.effectiveCameraId
        dialogBinding.spinnerCameraId.setSelection(cameraIds.indexOf(currentId).coerceAtLeast(0))

        dialogBinding.editHost.setText(sensorSettings.host)
        dialogBinding.editUdpPort.setText(sensorSettings.udpPort.toString())
        dialogBinding.editWsPort.setText(sensorSettings.wsPort.toString())
        dialogBinding.checkUseBinary.isChecked = sensorSettings.useBinary

        dialogBinding.spinnerTransport.adapter = ArrayAdapter(
            requireContext(),
            android.R.layout.simple_spinner_dropdown_item,
            transports
        )
        dialogBinding.spinnerTransport.setSelection(
            if (sensorSettings.transport == Transport.WEBSOCKET) 1 else 0
        )

        AlertDialog.Builder(requireContext())
            .setTitle(R.string.settings_title)
            .setView(dialogBinding.root)
            .setPositiveButton(R.string.settings_save) { _, _ ->
                val selectedId = cameraIds[dialogBinding.spinnerCameraId.selectedItemPosition]
                sensorSettings.cameraIdOverride = selectedId
                sensorSettings.host = dialogBinding.editHost.text.toString().trim()
                    .ifBlank { sensorSettings.host }
                sensorSettings.udpPort =
                    dialogBinding.editUdpPort.text.toString().toIntOrNull()
                        ?: sensorSettings.udpPort
                sensorSettings.wsPort =
                    dialogBinding.editWsPort.text.toString().toIntOrNull()
                        ?: sensorSettings.wsPort
                sensorSettings.transport =
                    if (dialogBinding.spinnerTransport.selectedItemPosition == 1) {
                        Transport.WEBSOCKET
                    } else {
                        Transport.UDP
                    }
                sensorSettings.useBinary = dialogBinding.checkUseBinary.isChecked

                // Restart stream so new destination / transport take effect
                val wasStreaming = streamCoordinator.isStreaming()
                streamCoordinator.stop()
                if (wasStreaming || viewModel.streamingEnabled) {
                    startStreaming()
                }
                refreshStatusLabels()
            }
            .setNeutralButton(R.string.settings_clear_override) { _, _ ->
                sensorSettings.cameraIdOverride = null
                refreshStatusLabels()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun maybePromptBatteryOptimization() {
        if (sensorSettings.batteryOptPrompted) return
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return
        val pm = requireContext().getSystemService(PowerManager::class.java) ?: return
        if (pm.isIgnoringBatteryOptimizations(requireContext().packageName)) return

        sensorSettings.batteryOptPrompted = true
        AlertDialog.Builder(requireContext())
            .setTitle(R.string.battery_opt_title)
            .setMessage(R.string.battery_opt_message)
            .setPositiveButton(android.R.string.ok) { _, _ ->
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:${requireContext().packageName}")
                }
                runCatching { startActivity(intent) }
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun setUpCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(requireContext())
        cameraProviderFuture.addListener(
            {
                cameraProvider = cameraProviderFuture.get()
                bindCameraUseCases()
            },
            ContextCompat.getMainExecutor(requireContext())
        )
    }

    @SuppressLint("UnsafeOptInUsageError")
    private fun bindCameraUseCases() {
        val cameraProvider = cameraProvider
            ?: throw IllegalStateException("Camera initialization failed.")

        val cameraSelector =
            CameraSelector.Builder()
                .requireLensFacing(CameraSelector.LENS_FACING_BACK)
                .build()

        val resolutionSelector = ResolutionSelector.Builder()
            .setResolutionStrategy(
                ResolutionStrategy(
                    CaptureConfig.ANALYSIS_SIZE,
                    ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER
                )
            )
            .build()

        preview = Preview.Builder()
            .setResolutionSelector(resolutionSelector)
            .setTargetRotation(fragmentCameraBinding.viewFinder.display.rotation)
            .build()

        val analysisBuilder = ImageAnalysis.Builder()
            .setResolutionSelector(resolutionSelector)
            .setTargetRotation(fragmentCameraBinding.viewFinder.display.rotation)
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_RGBA_8888)

        Camera2Interop.Extender(analysisBuilder)
            .setCaptureRequestOption(
                CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE,
                Range(CaptureConfig.TARGET_FPS, CaptureConfig.TARGET_FPS)
            )

        imageAnalyzer = analysisBuilder.build().also {
            it.setAnalyzer(backgroundExecutor) { image ->
                detectPose(image)
            }
        }

        cameraProvider.unbindAll()

        try {
            camera = cameraProvider.bindToLifecycle(
                this, cameraSelector, preview, imageAnalyzer
            )
            preview?.setSurfaceProvider(fragmentCameraBinding.viewFinder.surfaceProvider)
        } catch (exc: Exception) {
            Log.e(TAG, "Use case binding failed", exc)
        }
    }
    private var frameCounter = 0
    private fun detectPose(imageProxy: ImageProxy) {
        if (frameCounter++ % CaptureConfig.INFERENCE_EVERY_N_FRAMES != 0){
            imageProxy.close()
            return
        }
        if (this::poseLandmarkerHelper.isInitialized) {
            poseLandmarkerHelper.detectLiveStream(
                imageProxy = imageProxy,
                isFrontCamera = false
            )
        } else {
            imageProxy.close()
        }
    }

    override fun onConfigurationChanged(newConfig: Configuration) {
        super.onConfigurationChanged(newConfig)
        imageAnalyzer?.targetRotation =
            fragmentCameraBinding.viewFinder.display.rotation
    }

    override fun onResults(resultBundle: PoseLandmarkerHelper.ResultBundle) {
        val result = resultBundle.results.firstOrNull() ?: return
        if (this::streamCoordinator.isInitialized) {
            streamCoordinator.onPoseResult(
                result = result,
                imageWidth = resultBundle.inputImageWidth,
                imageHeight = resultBundle.inputImageHeight,
                inferenceMs = resultBundle.inferenceTime
            )
        }
    }

    override fun onError(error: String, errorCode: Int) {
        activity?.runOnUiThread {
            if (_fragmentCameraBinding != null) {
                fragmentCameraBinding.statusError.visibility = View.VISIBLE
                fragmentCameraBinding.statusError.text = error
            }
            Toast.makeText(requireContext(), error, Toast.LENGTH_SHORT).show()
            if (errorCode == PoseLandmarkerHelper.GPU_ERROR &&
                this::poseLandmarkerHelper.isInitialized
            ) {
                backgroundExecutor.execute {
                    poseLandmarkerHelper.currentDelegate =
                        PoseLandmarkerHelper.DELEGATE_CPU
                    poseLandmarkerHelper.clearPoseLandmarker()
                    poseLandmarkerHelper.setupPoseLandmarker()
                }
            }
        }
    }
}
