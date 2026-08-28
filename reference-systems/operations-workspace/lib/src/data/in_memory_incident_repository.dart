// SPDX-License-Identifier: Apache-2.0

import '../domain/incident.dart';

class InMemoryIncidentRepository implements IncidentRepository {
  InMemoryIncidentRepository(Iterable<Incident> incidents)
    : _items = {for (final incident in incidents) incident.id: incident};

  factory InMemoryIncidentRepository.seeded() {
    final baseline = DateTime.utc(2026, 8, 19, 12);
    return InMemoryIncidentRepository([
      Incident(
        id: 'inc-001',
        title: '同期Queueの遅延',
        description: 'Offline操作の再送が性能予算を超過しています。',
        status: IncidentStatus.investigating,
        updatedAt: baseline,
      ),
      Incident(
        id: 'inc-002',
        title: 'Desktop Keyboard確認',
        description: '主要操作へKeyboardだけで到達できるか確認します。',
        status: IncidentStatus.open,
        updatedAt: baseline.subtract(const Duration(hours: 1)),
      ),
    ]);
  }

  final Map<String, Incident> _items;

  @override
  Future<List<Incident>> list() async {
    final result = _items.values.toList()
      ..sort((left, right) => right.updatedAt.compareTo(left.updatedAt));
    return List.unmodifiable(result);
  }

  @override
  Future<void> save(Incident incident) async {
    _items[incident.id] = incident;
  }
}
