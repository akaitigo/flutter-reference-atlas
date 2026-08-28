// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
import 'package:operations_workspace/src/presentation/workspace_app.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('Simulator上で主要な状態遷移を実行する', (tester) async {
    await tester.pumpWidget(
      WorkspaceApp(repository: InMemoryIncidentRepository.seeded()),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('incident-detail')), findsOneWidget);
    await tester.tap(find.byKey(const Key('advance-status-button')));
    await tester.pumpAndSettle();
    expect(find.text('解決済み'), findsWidgets);
  });
}
