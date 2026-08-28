// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/data/in_memory_incident_repository.dart';
import 'package:operations_workspace/src/domain/incident.dart';
import 'package:operations_workspace/src/presentation/workspace_controller.dart';

void main() {
  test('loadと状態遷移がRepositoryを正本にする', () async {
    final repository = InMemoryIncidentRepository([
      Incident(
        id: 'inc-1',
        title: '検証',
        description: '状態遷移を検証する',
        status: IncidentStatus.open,
        updatedAt: DateTime.utc(2026, 8, 19),
      ),
    ]);
    final controller = WorkspaceController(
      repository: repository,
      clock: () => DateTime.utc(2026, 8, 20),
    );

    await controller.load();
    expect(controller.state.selected?.status, IncidentStatus.open);
    await controller.advanceSelected();
    expect(controller.state.selected?.status, IncidentStatus.investigating);
  });

  test('空件名は保存せずUI Messageへ変換する', () async {
    final repository = InMemoryIncidentRepository(const []);
    final controller = WorkspaceController(repository: repository);
    await controller.createIncident('  ');
    expect(controller.state.incidents, isEmpty);
    expect(controller.state.message, '件名を入力してください。');
  });
}
