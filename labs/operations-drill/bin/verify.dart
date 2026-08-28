// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

import 'package:operations_drill/operations_drill.dart';

Future<void> main() async {
  final root = await Directory.systemTemp.createTemp('flutter-atlas-ops-');
  try {
    const operations = SnapshotOperations();
    const legacy = WorkspaceSnapshot(
      schemaVersion: 1,
      items: <Map<String, Object?>>[
        <String, Object?>{'id': 'incident-001', 'status': 'open'},
      ],
    );
    final migrated = operations.migrate(legacy);
    if (legacy.schemaVersion != 1 ||
        legacy.items.single.containsKey('severity')) {
      throw StateError('migration mutated its input');
    }
    if (migrated.schemaVersion != 2 ||
        migrated.items.single['severity'] != 'medium') {
      throw StateError('migration result is invalid');
    }

    final backupFile = File('${root.path}/workspace.backup.json');
    await operations.backup(migrated, backupFile);
    final restored = await operations.restore(backupFile);
    if (jsonEncode(restored.toJson()) != jsonEncode(migrated.toJson())) {
      throw StateError('restored state differs from backup');
    }

    var invalidRestoreRejected = false;
    final corruptFile = File('${root.path}/corrupt.json');
    await corruptFile.writeAsString(
      '{"schema_version":2,"items":[',
      flush: true,
    );
    try {
      await operations.restore(corruptFile);
    } on FormatException {
      invalidRestoreRejected = true;
    }
    if (!invalidRestoreRejected) {
      throw StateError('corrupt backup was accepted');
    }

    var unsupportedMigrationRejected = false;
    try {
      operations.migrate(
        const WorkspaceSnapshot(
          schemaVersion: 99,
          items: <Map<String, Object?>>[],
        ),
      );
    } on StateError {
      unsupportedMigrationRejected = true;
    }
    if (!unsupportedMigrationRejected) {
      throw StateError('unsupported migration was accepted');
    }

    stdout.writeln(
      jsonEncode(<String, Object?>{
        'schema_version': 1,
        'lab_id': 'lab.operations-drill',
        'verdict': 'pass',
        'checks': <String, Object?>{
          'backup_round_trip': true,
          'input_immutable': true,
          'corrupt_restore_rejected': true,
          'unsupported_migration_rejected': true,
          'cleanup': true,
        },
      }),
    );
  } finally {
    if (await root.exists()) {
      await root.delete(recursive: true);
    }
  }
}
