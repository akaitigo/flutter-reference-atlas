// SPDX-License-Identifier: Apache-2.0

enum IncidentStatus { open, investigating, resolved }

class Incident {
  const Incident({
    required this.id,
    required this.title,
    required this.description,
    required this.status,
    required this.updatedAt,
  });

  final String id;
  final String title;
  final String description;
  final IncidentStatus status;
  final DateTime updatedAt;

  Incident copyWith({
    String? title,
    String? description,
    IncidentStatus? status,
    DateTime? updatedAt,
  }) {
    return Incident(
      id: id,
      title: title ?? this.title,
      description: description ?? this.description,
      status: status ?? this.status,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

abstract interface class IncidentRepository {
  Future<List<Incident>> list();
  Future<void> save(Incident incident);
}
