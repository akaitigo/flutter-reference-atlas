// SPDX-License-Identifier: Apache-2.0

class Revision {
  const Revision({
    required this.entityId,
    required this.baseVersion,
    required this.logicalClock,
    required this.actorId,
    required this.payload,
  });

  final String entityId;
  final int baseVersion;
  final int logicalClock;
  final String actorId;
  final String payload;
}

class Resolution {
  const Resolution({
    required this.winner,
    required this.conflictingActors,
    required this.lostUpdateDetected,
  });

  final Revision winner;
  final List<String> conflictingActors;
  final bool lostUpdateDetected;

  Map<String, Object> toJson() => {
    'winner_actor': winner.actorId,
    'winner_payload': winner.payload,
    'conflicting_actors': conflictingActors,
    'lost_update_detected': lostUpdateDetected,
  };
}

Resolution resolveRevisions(Iterable<Revision> input) {
  final revisions = input.toList();
  if (revisions.isEmpty) {
    throw ArgumentError.value(input, 'input', '1件以上必要です');
  }
  final entityIds = revisions.map((revision) => revision.entityId).toSet();
  if (entityIds.length != 1) {
    throw ArgumentError('異なるEntityのRevisionは同時に解決できません');
  }
  revisions.sort((left, right) {
    final clock = right.logicalClock.compareTo(left.logicalClock);
    if (clock != 0) return clock;
    return left.actorId.compareTo(right.actorId);
  });
  final winner = revisions.first;
  final concurrent =
      revisions
          .where(
            (revision) =>
                revision.baseVersion == winner.baseVersion &&
                revision.payload != winner.payload,
          )
          .map((revision) => revision.actorId)
          .toSet()
          .toList()
        ..sort();
  return Resolution(
    winner: winner,
    conflictingActors: List.unmodifiable(concurrent),
    lostUpdateDetected: concurrent.isNotEmpty,
  );
}
