// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/foundation.dart';

import '../domain/incident.dart';

@immutable
class WorkspaceState {
  const WorkspaceState({
    this.incidents = const [],
    this.selectedId,
    this.loading = false,
    this.message,
  });

  final List<Incident> incidents;
  final String? selectedId;
  final bool loading;
  final String? message;

  Incident? get selected {
    for (final incident in incidents) {
      if (incident.id == selectedId) return incident;
    }
    return null;
  }

  WorkspaceState copyWith({
    List<Incident>? incidents,
    String? selectedId,
    bool clearSelection = false,
    bool? loading,
    String? message,
    bool clearMessage = false,
  }) {
    return WorkspaceState(
      incidents: incidents ?? this.incidents,
      selectedId: clearSelection ? null : selectedId ?? this.selectedId,
      loading: loading ?? this.loading,
      message: clearMessage ? null : message ?? this.message,
    );
  }
}

class WorkspaceController extends ChangeNotifier {
  WorkspaceController({
    required IncidentRepository repository,
    DateTime Function()? clock,
  }) : _repository = repository,
       _clock = clock ?? DateTime.now;

  final IncidentRepository _repository;
  final DateTime Function() _clock;
  WorkspaceState _state = const WorkspaceState();

  WorkspaceState get state => _state;

  Future<void> load() async {
    _setState(_state.copyWith(loading: true, clearMessage: true));
    try {
      final incidents = await _repository.list();
      _setState(
        _state.copyWith(
          incidents: incidents,
          selectedId: _state.selectedId ?? incidents.firstOrNull?.id,
          loading: false,
        ),
      );
    } on Object {
      _setState(
        _state.copyWith(loading: false, message: '一覧を読み込めませんでした。再試行してください。'),
      );
    }
  }

  void select(String id) {
    if (_state.incidents.any((incident) => incident.id == id)) {
      _setState(_state.copyWith(selectedId: id, clearMessage: true));
    }
  }

  void clearSelection() {
    _setState(_state.copyWith(clearSelection: true));
  }

  Future<void> createIncident(String title) async {
    final trimmed = title.trim();
    if (trimmed.isEmpty) {
      _setState(_state.copyWith(message: '件名を入力してください。'));
      return;
    }
    final now = _clock().toUtc();
    final incident = Incident(
      id: 'inc-${now.microsecondsSinceEpoch}',
      title: trimmed,
      description: '新規登録されたインシデントです。',
      status: IncidentStatus.open,
      updatedAt: now,
    );
    await _repository.save(incident);
    await load();
    select(incident.id);
  }

  Future<void> advanceSelected() async {
    final current = _state.selected;
    if (current == null) return;
    final next = switch (current.status) {
      IncidentStatus.open => IncidentStatus.investigating,
      IncidentStatus.investigating => IncidentStatus.resolved,
      IncidentStatus.resolved => IncidentStatus.resolved,
    };
    if (next == current.status) return;
    await _repository.save(current.copyWith(status: next, updatedAt: _clock()));
    await load();
    select(current.id);
  }

  void _setState(WorkspaceState value) {
    _state = value;
    notifyListeners();
  }
}

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
