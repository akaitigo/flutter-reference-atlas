// SPDX-License-Identifier: Apache-2.0

import 'dart:async';

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
    expect(controller.state.failure?.message, '件名を入力してください。');
    expect(controller.canRetry, isFalse);
  });

  test('保存失敗は状態を壊さず同じ変更を再試行できる', () async {
    final repository = _FlakyRepository([
      Incident(
        id: 'inc-1',
        title: '検証',
        description: 'Recoveryを検証する',
        status: IncidentStatus.open,
        updatedAt: DateTime.utc(2026, 8, 19),
      ),
    ]);
    final controller = WorkspaceController(
      repository: repository,
      clock: () => DateTime.utc(2026, 8, 20),
    );
    await controller.load();
    repository.failNextSave = true;

    await controller.advanceSelected();

    expect(controller.state.selected?.status, IncidentStatus.open);
    expect(controller.state.failure?.operation, WorkspaceOperation.advance);
    expect(controller.canRetry, isTrue);

    await controller.retry();

    expect(controller.state.selected?.status, IncidentStatus.investigating);
    expect(controller.state.failure, isNull);
    expect(controller.state.announcement, '状態を調査中へ更新しました。');
    expect(repository.savedIds, ['inc-1']);
  });

  test('遅れて完了した古いloadは新しい状態を上書きしない', () async {
    final repository = _DeferredListRepository();
    final controller = WorkspaceController(repository: repository);

    final first = controller.load();
    final second = controller.load();
    repository.complete(1, [
      Incident(
        id: 'new',
        title: '新しい結果',
        description: '後から開始したRequest',
        status: IncidentStatus.open,
        updatedAt: DateTime.utc(2026, 8, 20),
      ),
    ]);
    await second;
    repository.complete(0, [
      Incident(
        id: 'old',
        title: '古い結果',
        description: '先に開始したRequest',
        status: IncidentStatus.open,
        updatedAt: DateTime.utc(2026, 8, 19),
      ),
    ]);
    await first;

    expect(controller.state.incidents.single.id, 'new');
  });

  test('dispose後に完了したloadは通知しない', () async {
    final repository = _DeferredListRepository();
    final controller = WorkspaceController(repository: repository);
    final future = controller.load();
    controller.dispose();

    repository.complete(0, const []);

    await expectLater(future, completes);
  });
}

class _FlakyRepository implements IncidentRepository {
  _FlakyRepository(Iterable<Incident> incidents)
    : _items = {for (final incident in incidents) incident.id: incident};

  final Map<String, Incident> _items;
  final List<String> savedIds = [];
  bool failNextSave = false;

  @override
  Future<List<Incident>> list() async => List.unmodifiable(_items.values);

  @override
  Future<void> save(Incident incident) async {
    if (failNextSave) {
      failNextSave = false;
      throw StateError('secret backend detail');
    }
    savedIds.add(incident.id);
    _items[incident.id] = incident;
  }
}

class _DeferredListRepository implements IncidentRepository {
  final List<Completer<List<Incident>>> _requests = [];

  @override
  Future<List<Incident>> list() {
    final completer = Completer<List<Incident>>();
    _requests.add(completer);
    return completer.future;
  }

  void complete(int index, List<Incident> incidents) {
    _requests[index].complete(incidents);
  }

  @override
  Future<void> save(Incident incident) async {}
}
