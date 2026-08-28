// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
import 'package:operations_workspace/src/domain/incident.dart';
import 'package:operations_workspace/src/observability/frame_performance_monitor.dart';
import 'package:operations_workspace/src/presentation/workspace_app.dart';

void main() {
  testWidgets('広幅では一覧と詳細を同時表示し状態遷移できる', (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      WorkspaceApp(repository: InMemoryIncidentRepository.seeded()),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('incident-list')), findsOneWidget);
    expect(find.byKey(const Key('incident-detail')), findsOneWidget);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    expect(find.text('解決済み'), findsWidgets);
  });

  testWidgets('Dialogから新規インシデントを追加できる', (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(
      WorkspaceApp(repository: InMemoryIncidentRepository.seeded()),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('create-button')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('incident-title-field')),
      '新しい障害',
    );
    await tester.tap(find.byKey(const Key('save-incident-button')));
    await tester.pumpAndSettle();
    expect(find.text('新しい障害'), findsWidgets);
  });

  testWidgets('公開Navigator routeで診断へ移動しPerformanceを観測できる', (tester) async {
    final monitor = FramePerformanceMonitor();
    addTearDown(monitor.dispose);
    monitor.recordTotalSpan(const Duration(milliseconds: 20));
    await tester.pumpWidget(
      WorkspaceApp(
        repository: InMemoryIncidentRepository.seeded(),
        performanceMonitor: monitor,
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('diagnostics-button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('diagnostics-screen')), findsOneWidget);
    expect(find.textContaining('入力境界'), findsOneWidget);
    expect(find.textContaining('予算超過を観測'), findsOneWidget);
    expect(
      ModalRoute.of(
        tester.element(find.byKey(const Key('diagnostics-screen'))),
      )?.settings.name,
      WorkspaceRoutes.diagnostics,
    );

    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('incident-list')), findsOneWidget);
  });

  testWidgets('Repository失敗を秘匿して再試行から回復する', (tester) async {
    tester.view.physicalSize = const Size(1200, 800);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final repository = _FailOnceRepository();
    await tester.pumpWidget(WorkspaceApp(repository: repository));
    await tester.pumpAndSettle();
    repository.failNextSave = true;

    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('failure-banner')), findsOneWidget);
    expect(find.textContaining('sensitive-diagnostic'), findsNothing);
    expect(find.text('未対応'), findsWidgets);

    await tester.tap(find.byKey(const Key('retry-button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('failure-banner')), findsNothing);
    expect(find.byKey(const Key('status-announcement')), findsOneWidget);
    expect(find.text('調査中'), findsWidgets);
  });
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
