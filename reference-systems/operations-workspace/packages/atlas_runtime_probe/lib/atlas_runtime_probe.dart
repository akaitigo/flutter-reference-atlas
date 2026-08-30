// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/services.dart';

enum ProbeCodecVariant { standard, json }

class RuntimeProbeSnapshot {
  const RuntimeProbeSnapshot({
    required this.platform,
    required this.osVersion,
    required this.sdkInt,
    required this.attachedToActivity,
    required this.codec,
  });

  factory RuntimeProbeSnapshot.fromMap(Map<Object?, Object?> value) {
    return RuntimeProbeSnapshot(
      platform: value['platform']! as String,
      osVersion: value['osVersion']! as String,
      sdkInt: value['sdkInt']! as int,
      attachedToActivity: value['attachedToActivity']! as bool,
      codec: value['codec']! as String,
    );
  }

  final String platform;
  final String osVersion;
  final int sdkInt;
  final bool attachedToActivity;
  final String codec;
}

class AtlasRuntimeProbe {
  AtlasRuntimeProbe({this.variant = ProbeCodecVariant.standard});

  final ProbeCodecVariant variant;

  MethodChannel get _channel => switch (variant) {
    ProbeCodecVariant.standard => const MethodChannel(
      'dev.akaitigo.atlas/runtime_probe/standard',
    ),
    ProbeCodecVariant.json => const MethodChannel(
      'dev.akaitigo.atlas/runtime_probe/json',
      JSONMethodCodec(),
    ),
  };

  Future<RuntimeProbeSnapshot> snapshot() async {
    final value = await _channel.invokeMethod<Map<Object?, Object?>>(
      'runtimeInfo',
    );
    if (value == null) {
      throw const FormatException('runtimeInfo result is null');
    }
    return RuntimeProbeSnapshot.fromMap(value);
  }

  Future<String> echo(String value) async {
    final result = await _channel.invokeMethod<String>('echo', value);
    if (result == null) throw const FormatException('echo result is null');
    return result;
  }

  Future<void> requestDenied() => _channel.invokeMethod<void>('requestDenied');

  Future<String> transientOperation() async {
    final result = await _channel.invokeMethod<String>('transientOperation');
    if (result == null) {
      throw const FormatException('transientOperation result is null');
    }
    return result;
  }
}
