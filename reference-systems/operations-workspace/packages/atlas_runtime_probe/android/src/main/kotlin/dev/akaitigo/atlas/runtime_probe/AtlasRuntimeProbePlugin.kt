// SPDX-License-Identifier: Apache-2.0
package dev.akaitigo.atlas.runtime_probe

import android.app.Activity
import android.os.Build
import io.flutter.embedding.engine.plugins.FlutterPlugin
import io.flutter.embedding.engine.plugins.activity.ActivityAware
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding
import io.flutter.plugin.common.JSONMethodCodec
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.StandardMethodCodec

class AtlasRuntimeProbePlugin : FlutterPlugin, ActivityAware {
    private val channels = mutableListOf<MethodChannel>()
    private val transientFailures = mutableSetOf<String>()
    private var activity: Activity? = null

    override fun onAttachedToEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        registerChannel(
            MethodChannel(
                binding.binaryMessenger,
                "dev.akaitigo.atlas/runtime_probe/standard",
                StandardMethodCodec.INSTANCE,
            ),
            "standard",
        )
        registerChannel(
            MethodChannel(
                binding.binaryMessenger,
                "dev.akaitigo.atlas/runtime_probe/json",
                JSONMethodCodec.INSTANCE,
            ),
            "json",
        )
    }

    private fun registerChannel(channel: MethodChannel, codec: String) {
        channel.setMethodCallHandler { call, result -> handle(codec, call, result) }
        channels.add(channel)
    }

    private fun handle(codec: String, call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "runtimeInfo" -> result.success(
                mapOf(
                    "platform" to "Android",
                    "osVersion" to Build.VERSION.RELEASE,
                    "sdkInt" to Build.VERSION.SDK_INT,
                    "attachedToActivity" to (activity != null),
                    "codec" to codec,
                ),
            )
            "echo" -> {
                val value = call.arguments as? String
                when {
                    value == null -> result.error("INVALID_ARGUMENT", "Stringが必要です。", null)
                    value.length > 64 -> result.error("BOUNDARY_EXCEEDED", "64文字以下が必要です。", null)
                    else -> result.success(value)
                }
            }
            "requestDenied" -> result.error("PERMISSION_DENIED", "fixture policy denial", null)
            "transientOperation" -> {
                if (transientFailures.add(codec)) {
                    result.error("TRANSIENT_FAILURE", "retry is safe", null)
                } else {
                    result.success("recovered")
                }
            }
            else -> result.notImplemented()
        }
    }

    override fun onDetachedFromEngine(binding: FlutterPlugin.FlutterPluginBinding) {
        channels.forEach { it.setMethodCallHandler(null) }
        channels.clear()
        transientFailures.clear()
    }

    override fun onAttachedToActivity(binding: ActivityPluginBinding) {
        activity = binding.activity
    }

    override fun onDetachedFromActivityForConfigChanges() {
        activity = null
    }

    override fun onReattachedToActivityForConfigChanges(binding: ActivityPluginBinding) {
        activity = binding.activity
    }

    override fun onDetachedFromActivity() {
        activity = null
    }
}
