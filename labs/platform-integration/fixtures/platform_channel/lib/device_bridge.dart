// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/services.dart';

final class DeviceBridge {
  const DeviceBridge();

  static const MethodChannel _channel = MethodChannel(
    'dev.flutter.reference_atlas/device',
  );

  Future<String?> getPlatformVersion() =>
      _channel.invokeMethod<String>('getPlatformVersion');
}
