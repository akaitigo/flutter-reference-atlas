// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';

import '../lib/conflict_resolver.dart';

void main() {
  const first = Revision(
    entityId: 'incident-42',
    baseVersion: 7,
    logicalClock: 9,
    actorId: 'device-a',
    payload: 'investigating',
  );
  const second = Revision(
    entityId: 'incident-42',
    baseVersion: 7,
    logicalClock: 9,
    actorId: 'device-b',
    payload: 'resolved',
  );
  final forward = resolveRevisions([first, second]);
  final reverse = resolveRevisions([second, first]);
  if (jsonEncode(forward.toJson()) != jsonEncode(reverse.toJson())) {
    throw StateError('入力順序により競合解決結果が変化しました');
  }
  if (!forward.lostUpdateDetected || forward.winner.actorId != 'device-a') {
    throw StateError('Lost update検出またはtie-break契約に違反しました');
  }
  print(
    jsonEncode({
      'schema_version': 1,
      'lab_id': 'lab.offline-conflict-resolution',
      'verdict': 'pass',
      'resolution': forward.toJson(),
    }),
  );
}
