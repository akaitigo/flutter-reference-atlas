// SPDX-License-Identifier: Apache-2.0

import Flutter
import UIKit

public class DeviceBridgePlugin: NSObject, FlutterPlugin {
  public static func register(with registrar: FlutterPluginRegistrar) {
    let channel = FlutterMethodChannel(
      name: "dev.flutter.reference_atlas/device",
      binaryMessenger: registrar.messenger()
    )
    let instance = DeviceBridgePlugin()
    registrar.addMethodCallDelegate(instance, channel: channel)
  }

  public func handle(_ call: FlutterMethodCall, result: @escaping FlutterResult) {
    if call.method == "getPlatformVersion" {
      result(UIDevice.current.systemVersion)
    } else {
      result(FlutterMethodNotImplemented)
    }
  }
}
