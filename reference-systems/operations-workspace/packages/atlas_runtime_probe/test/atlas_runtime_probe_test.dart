// SPDX-License-Identifier: Apache-2.0

import 'package:atlas_runtime_probe/atlas_runtime_probe.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  for (final variant in ProbeCodecVariant.values) {
    final channel = switch (variant) {
      ProbeCodecVariant.standard => const MethodChannel(
        'dev.akaitigo.atlas/runtime_probe/standard',
      ),
      ProbeCodecVariant.json => const MethodChannel(
        'dev.akaitigo.atlas/runtime_probe/json',
        JSONMethodCodec(),
      ),
    };

    test('$variant maps runtime snapshot', () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            return <String, Object>{
              'platform': 'fixture',
              'osVersion': '1',
              'sdkInt': 1,
              'attachedToActivity': true,
              'codec': variant.name,
            };
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );

      final snapshot = await AtlasRuntimeProbe(variant: variant).snapshot();
      expect(snapshot.platform, 'fixture');
      expect(snapshot.codec, variant.name);
      expect(snapshot.attachedToActivity, isTrue);
    });
  }
}
