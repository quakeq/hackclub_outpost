package com.google.mediapipe.examples.poselandmarker.fragment

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.fragment.app.Fragment
import androidx.lifecycle.lifecycleScope
import androidx.navigation.Navigation
import com.google.mediapipe.examples.poselandmarker.R

class PermissionsFragment : Fragment() {

    private val requestPermissionLauncher =
        registerForActivityResult(
            ActivityResultContracts.RequestMultiplePermissions()
        ) { grants ->
            val cameraGranted = grants[Manifest.permission.CAMERA] == true
            if (cameraGranted) {
                navigateToCamera()
            } else {
                Toast.makeText(
                    context,
                    "Camera permission is required",
                    Toast.LENGTH_LONG
                ).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (hasPermissions(requireContext())) {
            navigateToCamera()
        } else {
            requestPermissionLauncher.launch(requiredPermissions())
        }
    }

    private fun navigateToCamera() {
        lifecycleScope.launchWhenStarted {
            Navigation.findNavController(
                requireActivity(),
                R.id.fragment_container
            ).navigate(
                R.id.action_permissions_to_camera
            )
        }
    }

    companion object {
        fun requiredPermissions(): Array<String> {
            return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                arrayOf(Manifest.permission.CAMERA, Manifest.permission.POST_NOTIFICATIONS)
            } else {
                arrayOf(Manifest.permission.CAMERA)
            }
        }

        fun hasPermissions(context: Context): Boolean {
            val cameraOk = ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.CAMERA
            ) == PackageManager.PERMISSION_GRANTED
            // Notifications are optional; camera is required
            return cameraOk
        }
    }
}
