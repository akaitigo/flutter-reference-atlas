// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:atlas_runtime_probe/atlas_runtime_probe.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
import 'package:operations_workspace/src/presentation/workspace_app.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Device runner上で主要な状態遷移を実行する', (tester) async {
    await tester.pumpWidget(
      WorkspaceApp(repository: InMemoryIncidentRepository.seeded()),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('incident-detail')), findsOneWidget);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    expect(find.text('解決済み'), findsWidgets);

    await tester.tap(find.byKey(const Key('diagnostics-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('diagnostics-screen')), findsOneWidget);
    expect(find.text('入力境界'), findsOneWidget);
    expect(find.byKey(const Key('performance-card')), findsOneWidget);

    await tester.tap(find.byKey(const Key('probe-platform-button')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Android'), findsOneWidget);
    expect(find.textContaining('Activity attached'), findsOneWidget);
  });

  for (final variant in ProbeCodecVariant.values) {
    testWidgets('MethodChannel $variant の正常・境界・拒否・障害・回復', (tester) async {
      final probe = AtlasRuntimeProbe(variant: variant);
      final boundary = List.filled(64, 'x').join();
      final overBoundary = List.filled(65, 'x').join();
      final snapshot = await probe.snapshot();
      expect(snapshot.platform, 'Android');
      expect(snapshot.attachedToActivity, isTrue);
      expect(snapshot.codec, variant.name);

      expect(await probe.echo(boundary), boundary);
      await expectLater(
        probe.echo(overBoundary),
        throwsA(
          isA<PlatformException>().having(
            (error) => error.code,
            'code',
            'BOUNDARY_EXCEEDED',
          ),
        ),
      );
      await expectLater(
        probe.requestDenied(),
        throwsA(
          isA<PlatformException>().having(
            (error) => error.code,
            'code',
            'PERMISSION_DENIED',
          ),
        ),
      );
      await expectLater(
        probe.transientOperation(),
        throwsA(
          isA<PlatformException>().having(
            (error) => error.code,
            'code',
            'TRANSIENT_FAILURE',
          ),
        ),
      );
      expect(await probe.transientOperation(), 'recovered');
    });
  }
}
