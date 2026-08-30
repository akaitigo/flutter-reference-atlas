// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
import 'package:operations_workspace/src/data/incident_snapshot_migration.dart';
import 'package:operations_workspace/src/domain/incident.dart';
import 'package:operations_workspace/src/observability/frame_performance_monitor.dart';
import 'package:operations_workspace/src/platform/platform_capability_probe.dart';
import 'package:operations_workspace/src/presentation/workspace_app.dart';

void main() {
  testWidgets('[scenario:normal] adaptive workspace state transition', (
    tester,
  ) async {
    await _pumpWorkspace(tester, size: const Size(1200, 800));
    expect(find.byKey(const Key('incident-list')), findsOneWidget);
    expect(find.byKey(const Key('incident-detail')), findsOneWidget);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    expect(find.text('解決済み'), findsWidgets);
  });

  testWidgets('[scenario:boundary] narrow layout preserves navigation', (
    tester,
  ) async {
    await _pumpWorkspace(tester, size: const Size(390, 844));
    expect(find.byKey(const Key('incident-detail')), findsOneWidget);
    expect(find.text('一覧へ'), findsOneWidget);
    await tester.tap(find.text('一覧へ'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('incident-list')), findsOneWidget);
  });

  testWidgets('[scenario:refusal] bidi control input is rejected', (
    tester,
  ) async {
    await _pumpWorkspace(tester);
    await tester.tap(find.byKey(const Key('create-button')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('incident-title-field')),
      '拒否対象\u202e',
    );
    await tester.tap(find.byKey(const Key('save-incident-button')));
    await tester.pumpAndSettle();
    expect(find.textContaining('利用できない制御文字'), findsOneWidget);
    expect(find.textContaining('拒否対象'), findsNothing);
  });

  testWidgets('[scenario:failure] repository detail is not disclosed', (
    tester,
  ) async {
    final repository = _FailOnceRepository()..failNextSave = true;
    await _pumpWorkspace(tester, repository: repository);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failure-banner')), findsOneWidget);
    expect(find.textContaining('sensitive-diagnostic'), findsNothing);
    expect(find.text('未対応'), findsWidgets);
  });

  testWidgets('[scenario:recovery] retry preserves intent and completes', (
    tester,
  ) async {
    final repository = _FailOnceRepository()..failNextSave = true;
    await _pumpWorkspace(tester, repository: repository);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('retry-button')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('failure-banner')), findsNothing);
    expect(find.text('調査中'), findsWidgets);
  });

  testWidgets('[scenario:migration] v1 snapshot maps into current domain', (
    tester,
  ) async {
    final incidents = IncidentSnapshotMigration.migrate({
      'schema_version': 1,
      'incidents': <Object?>[
        <String, Object?>{
          'id': 'legacy-1',
          'title': '移行済みインシデント',
          'description': 'v1 snapshot fixture',
          'status': 'investigating',
          'updated_at': '2026-08-19T00:00:00Z',
        },
      ],
    });
    await _pumpWorkspace(
      tester,
      repository: InMemoryIncidentRepository(incidents),
    );
    expect(find.text('移行済みインシデント'), findsWidgets);
    expect(find.text('調査中'), findsWidgets);
  });

  testWidgets('[scenario:operations] owned callbacks stop on unmount', (
    tester,
  ) async {
    final monitor = FramePerformanceMonitor();
    addTearDown(monitor.dispose);
    await _pumpWorkspace(tester, performanceMonitor: monitor);
    expect(monitor.isStarted, isTrue);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
    expect(monitor.isStarted, isFalse);
  });

  testWidgets('[scenario:security] diagnostics exposes bounded input policy', (
    tester,
  ) async {
    await _pumpWorkspace(tester, platformProbe: const _FixturePlatformProbe());
    await tester.tap(find.byKey(const Key('diagnostics-button')));
    await tester.pumpAndSettle();
    expect(find.text('入力境界'), findsOneWidget);
    expect(find.textContaining('双方向表示制御を拒否'), findsOneWidget);
    expect(find.textContaining('Repository例外の詳細はUIへ公開しません'), findsOneWidget);
  });

  testWidgets('[scenario:performance] frame budget breach is observable', (
    tester,
  ) async {
    final monitor = FramePerformanceMonitor();
    addTearDown(monitor.dispose);
    monitor.recordTotalSpan(const Duration(milliseconds: 20));
    await _pumpWorkspace(
      tester,
      performanceMonitor: monitor,
      platformProbe: const _FixturePlatformProbe(),
    );
    await tester.tap(find.byKey(const Key('diagnostics-button')));
    await tester.pumpAndSettle();
    expect(find.textContaining('予算超過を観測'), findsOneWidget);
    expect(find.textContaining('sample 1'), findsOneWidget);
  });

  testWidgets(
    '[scenario:compatibility] platform adapter result remains observable',
    (tester) async {
      await _pumpWorkspace(
        tester,
        platformProbe: const _FixturePlatformProbe(),
      );
      await tester.tap(find.byKey(const Key('diagnostics-button')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('probe-platform-button')));
      await tester.pumpAndSettle();
      expect(find.textContaining('web-runtime 151'), findsOneWidget);
      expect(find.textContaining('codec fixture'), findsOneWidget);
    },
  );
}

Future<void> _pumpWorkspace(
  WidgetTester tester, {
  IncidentRepository? repository,
  Size size = const Size(1200, 800),
  FramePerformanceMonitor? performanceMonitor,
  PlatformCapabilityProbe? platformProbe,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(
    WorkspaceApp(
      repository: repository ?? InMemoryIncidentRepository.seeded(),
      performanceMonitor: performanceMonitor,
      platformProbe: platformProbe,
    ),
  );
  await tester.pumpAndSettle();
}

class _FixturePlatformProbe implements PlatformCapabilityProbe {
  const _FixturePlatformProbe();

  @override
  Future<PlatformCapabilitySnapshot> inspect() async {
    return const PlatformCapabilitySnapshot(
      platform: 'web-runtime',
      osVersion: '151',
      sdkInt: 0,
      activityAttached: false,
      codec: 'fixture',
    );
  }
}

class _FailOnceRepository implements IncidentRepository {
  final Map<String, Incident> _items = {
    'inc-1': Incident(
      id: 'inc-1',
      title: '回復確認',
      description: '失敗からの回復を確認します。',
      status: IncidentStatus.open,
      updatedAt: DateTime.utc(2026, 8, 19),
    ),
  };
  bool failNextSave = false;

  @override
  Future<List<Incident>> list() async => List.unmodifiable(_items.values);

  @override
  Future<void> save(Incident incident) async {
    if (failNextSave) {
      failNextSave = false;
      throw StateError('sensitive-diagnostic=fixture-value');
    }
    _items[incident.id] = incident;
  }
}
