// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
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
}
