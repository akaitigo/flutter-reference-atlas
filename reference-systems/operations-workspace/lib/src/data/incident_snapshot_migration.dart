// SPDX-License-Identifier: Apache-2.0

import '../domain/incident.dart';

/// Reference App内の旧Snapshotを現行Domainへ移す、version固定の境界。
abstract final class IncidentSnapshotMigration {
  static const int currentSchemaVersion = 2;

  static List<Incident> migrate(Map<String, Object?> snapshot) {
    final version = snapshot['schema_version'];
    if (version != 1 && version != currentSchemaVersion) {
      throw const FormatException('unsupported incident snapshot schema');
    }
    final rows = snapshot['incidents'];
    if (rows is! List<Object?>) {
      throw const FormatException('incident snapshot rows are missing');
    }
    return List.unmodifiable(
      rows.map((row) {
        if (row is! Map<String, Object?>) {
          throw const FormatException('incident snapshot row is invalid');
        }
        final statusName = row['status'];
        final status = switch (statusName) {
          'open' => IncidentStatus.open,
          'investigating' => IncidentStatus.investigating,
          'resolved' => IncidentStatus.resolved,
          _ => throw const FormatException('incident status is invalid'),
        };
        final updatedAt = DateTime.tryParse(row['updated_at'] as String? ?? '');
        if (updatedAt == null) {
          throw const FormatException('incident timestamp is invalid');
        }
        return Incident(
          id: row['id'] as String? ?? '',
          title: row['title'] as String? ?? '',
          description: row['description'] as String? ?? '',
          status: status,
          updatedAt: updatedAt.toUtc(),
        );
      }),
    );
  }
}
