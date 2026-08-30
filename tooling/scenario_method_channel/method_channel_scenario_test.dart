// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';

import 'package:atlas_runtime_probe/atlas_runtime_probe.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

const scenario = String.fromEnvironment('ATLAS_SCENARIO');
const variantName = String.fromEnvironment('ATLAS_VARIANT');

Future<String> platformErrorCode(Future<void> operation) async {
  try {
    await operation;
  } on PlatformException catch (error) {
    return error.code;
  }
  throw StateError('PlatformExceptionが必要です。');
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  if (!const {'boundary', 'refusal', 'failure', 'recovery'}.contains(scenario)) {
    throw StateError('未対応Scenarioです: $scenario');
  }
  final variant = ProbeCodecVariant.values.byName(variantName);

  testWidgets('platform.method-channel $scenario $variantName', (tester) async {
    final probe = AtlasRuntimeProbe(variant: variant);
    final snapshot = await probe.snapshot();
    expect(snapshot.platform, 'Android');
    expect(snapshot.attachedToActivity, isTrue);
    expect(snapshot.codec, variantName);

    final observed = <String, Object?>{
      'surface_id': 'platform.method-channel',
      'scenario': scenario,
      'variant': variantName,
      'platform': snapshot.platform,
      'os_version': snapshot.osVersion,
      'api_level': snapshot.sdkInt,
      'activity_attached': snapshot.attachedToActivity,
      'codec': snapshot.codec,
    };

    switch (scenario) {
      case 'boundary':
        final accepted = List.filled(64, 'x').join();
        final rejected = List.filled(65, 'x').join();
        expect(await probe.echo(accepted), accepted);
        final code = await platformErrorCode(probe.echo(rejected).then((_) {}));
        expect(code, 'BOUNDARY_EXCEEDED');
        observed.addAll({
          'accepted_length': accepted.length,
          'rejected_length': rejected.length,
          'error_code': code,
        });
        break;
      case 'refusal':
        final code = await platformErrorCode(probe.requestDenied());
        expect(code, 'PERMISSION_DENIED');
        observed['error_code'] = code;
        break;
      case 'failure':
        final code = await platformErrorCode(probe.transientOperation().then((_) {}));
        expect(code, 'TRANSIENT_FAILURE');
        observed['error_code'] = code;
        break;
      case 'recovery':
        final code = await platformErrorCode(probe.transientOperation().then((_) {}));
        expect(code, 'TRANSIENT_FAILURE');
        final recovered = await probe.transientOperation();
        expect(recovered, 'recovered');
        observed.addAll({'first_error_code': code, 'recovered_value': recovered});
        break;
    }

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: Center(
            child: Text(
              'platform.method-channel\n$scenario\n$variantName\nPASS',
              textDirection: TextDirection.ltr,
            ),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    debugPrint('ATLAS_SCENARIO_OBSERVATION:${jsonEncode(observed)}');
    // Host Harnessが実Android画面を取得するまで表示を維持する。
    await Future<void>.delayed(const Duration(seconds: 3));
  });
}
