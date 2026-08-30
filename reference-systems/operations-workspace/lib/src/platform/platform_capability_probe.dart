// SPDX-License-Identifier: Apache-2.0

import 'package:atlas_runtime_probe/atlas_runtime_probe.dart';

class PlatformCapabilitySnapshot {
  const PlatformCapabilitySnapshot({
    required this.platform,
    required this.osVersion,
    required this.sdkInt,
    required this.activityAttached,
    required this.codec,
  });

  final String platform;
  final String osVersion;
  final int sdkInt;
  final bool activityAttached;
  final String codec;
}

abstract interface class PlatformCapabilityProbe {
  Future<PlatformCapabilitySnapshot> inspect();
}

class MethodChannelPlatformCapabilityProbe implements PlatformCapabilityProbe {
  MethodChannelPlatformCapabilityProbe({AtlasRuntimeProbe? probe})
    : _probe = probe ?? AtlasRuntimeProbe();

  final AtlasRuntimeProbe _probe;

  @override
  Future<PlatformCapabilitySnapshot> inspect() async {
    final value = await _probe.snapshot();
    return PlatformCapabilitySnapshot(
      platform: value.platform,
      osVersion: value.osVersion,
      sdkInt: value.sdkInt,
      activityAttached: value.attachedToActivity,
      codec: value.codec,
    );
  }
}
