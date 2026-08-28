// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

final class WorkspaceSnapshot {
  const WorkspaceSnapshot({required this.schemaVersion, required this.items});

  final int schemaVersion;
  final List<Map<String, Object?>> items;

  Map<String, Object?> toJson() => <String, Object?>{
    'schema_version': schemaVersion,
    'items': items,
  };

  static WorkspaceSnapshot parse(String source) {
    final Object? decoded = jsonDecode(source);
    if (decoded is! Map<String, Object?>) {
      throw const FormatException('snapshot root must be an object');
    }
    final Object? rawVersion = decoded['schema_version'];
    final Object? rawItems = decoded['items'];
    if (rawVersion is! int || rawItems is! List<Object?>) {
      throw const FormatException('snapshot schema is invalid');
    }
    final items = rawItems
        .map((Object? value) {
          if (value is! Map<String, Object?>) {
            throw const FormatException('snapshot item must be an object');
          }
          return Map<String, Object?>.unmodifiable(value);
        })
        .toList(growable: false);
    return WorkspaceSnapshot(schemaVersion: rawVersion, items: items);
  }
}

final class SnapshotOperations {
  const SnapshotOperations();

  Future<File> backup(WorkspaceSnapshot snapshot, File destination) async {
    final file = await destination.writeAsString(
      '${jsonEncode(snapshot.toJson())}\n',
      flush: true,
    );
    WorkspaceSnapshot.parse(await file.readAsString());
    return file;
  }

  Future<WorkspaceSnapshot> restore(File source) async {
    final snapshot = WorkspaceSnapshot.parse(await source.readAsString());
    if (snapshot.schemaVersion != 2) {
      throw StateError('restore requires schema version 2');
    }
    return snapshot;
  }

  WorkspaceSnapshot migrate(WorkspaceSnapshot source) {
    if (source.schemaVersion == 2) {
      return source;
    }
    if (source.schemaVersion != 1) {
      throw StateError('unsupported schema version ${source.schemaVersion}');
    }
    return WorkspaceSnapshot(
      schemaVersion: 2,
      items: source.items
          .map(
            (Map<String, Object?> item) => <String, Object?>{
              ...item,
              'severity': item['severity'] ?? 'medium',
            },
          )
          .toList(growable: false),
    );
  }
}
