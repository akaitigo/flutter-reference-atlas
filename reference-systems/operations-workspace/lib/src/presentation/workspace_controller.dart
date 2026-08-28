// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/foundation.dart';

import '../domain/incident.dart';
import '../domain/incident_input_policy.dart';

enum WorkspaceOperation { load, create, advance }

@immutable
class WorkspaceFailure {
  const WorkspaceFailure({required this.operation, required this.message});

  final WorkspaceOperation operation;
  final String message;
}

@immutable
class WorkspaceState {
  const WorkspaceState({
    this.incidents = const [],
    this.selectedId,
    this.loading = false,
    this.saving = false,
    this.failure,
    this.announcement,
  });

  final List<Incident> incidents;
  final String? selectedId;
  final bool loading;
  final bool saving;
  final WorkspaceFailure? failure;
  final String? announcement;

  bool get busy => loading || saving;

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
    bool? saving,
    WorkspaceFailure? failure,
    bool clearFailure = false,
    String? announcement,
    bool clearAnnouncement = false,
  }) {
    return WorkspaceState(
      incidents: incidents ?? this.incidents,
      selectedId: clearSelection ? null : selectedId ?? this.selectedId,
      loading: loading ?? this.loading,
      saving: saving ?? this.saving,
      failure: clearFailure ? null : failure ?? this.failure,
      announcement: clearAnnouncement
          ? null
          : announcement ?? this.announcement,
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
  Future<void> Function()? _retry;
  int _revision = 0;
  bool _disposed = false;

  WorkspaceState get state => _state;
  bool get canRetry => _retry != null;

  Future<void> load() async {
    final revision = ++_revision;
    _retry = null;
    _setState(
      _state.copyWith(
        loading: true,
        clearFailure: true,
        clearAnnouncement: true,
      ),
    );
    try {
      final incidents = await _repository.list();
      if (revision != _revision) return;
      final selectedId =
          incidents.any((incident) => incident.id == _state.selectedId)
          ? _state.selectedId
          : incidents.firstOrNull?.id;
      _setState(
        _state.copyWith(
          incidents: List.unmodifiable(incidents),
          selectedId: selectedId,
          clearSelection: selectedId == null,
          loading: false,
          clearFailure: true,
        ),
      );
    } on Object {
      if (revision != _revision) return;
      _retry = load;
      _setState(
        _state.copyWith(
          loading: false,
          failure: const WorkspaceFailure(
            operation: WorkspaceOperation.load,
            message: '一覧を読み込めませんでした。安全に再試行できます。',
          ),
        ),
      );
    }
  }

  void select(String id) {
    if (_state.incidents.any((incident) => incident.id == id)) {
      _setState(
        _state.copyWith(
          selectedId: id,
          clearFailure: true,
          clearAnnouncement: true,
        ),
      );
    }
  }

  void clearSelection() {
    _setState(_state.copyWith(clearSelection: true));
  }

  Future<void> createIncident(String title) async {
    final validation = IncidentTitlePolicy.validate(title);
    if (!validation.isAccepted) {
      _setState(
        _state.copyWith(
          failure: WorkspaceFailure(
            operation: WorkspaceOperation.create,
            message: validation.error!,
          ),
          clearAnnouncement: true,
        ),
      );
      return;
    }
    final now = _clock().toUtc();
    final incident = Incident(
      id: 'inc-${now.microsecondsSinceEpoch}',
      title: validation.value!,
      description: '新規登録されたインシデントです。',
      status: IncidentStatus.open,
      updatedAt: now,
    );
    await _saveAndReload(
      incident,
      operation: WorkspaceOperation.create,
      successMessage: 'インシデントを追加しました。',
    );
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
    await _saveAndReload(
      current.copyWith(status: next, updatedAt: _clock().toUtc()),
      operation: WorkspaceOperation.advance,
      successMessage: '状態を${_statusLabel(next)}へ更新しました。',
    );
  }

  Future<void> retry() async {
    final retry = _retry;
    if (retry == null || _state.busy) return;
    await retry();
  }

  void dismissAnnouncement() {
    _setState(_state.copyWith(clearAnnouncement: true));
  }

  void dismissFailure() {
    _retry = null;
    _setState(_state.copyWith(clearFailure: true));
  }

  Future<void> _saveAndReload(
    Incident incident, {
    required WorkspaceOperation operation,
    required String successMessage,
  }) async {
    final revision = ++_revision;
    _retry = null;
    _setState(
      _state.copyWith(
        saving: true,
        clearFailure: true,
        clearAnnouncement: true,
      ),
    );
    try {
      await _repository.save(incident);
      final incidents = await _repository.list();
      if (revision != _revision) return;
      _setState(
        _state.copyWith(
          incidents: List.unmodifiable(incidents),
          selectedId: incident.id,
          saving: false,
          clearFailure: true,
          announcement: successMessage,
        ),
      );
    } on Object {
      if (revision != _revision) return;
      _retry = () => _saveAndReload(
        incident,
        operation: operation,
        successMessage: successMessage,
      );
      _setState(
        _state.copyWith(
          saving: false,
          failure: WorkspaceFailure(
            operation: operation,
            message: '変更を保存できませんでした。内容を保持したまま再試行できます。',
          ),
        ),
      );
    }
  }

  void _setState(WorkspaceState value) {
    if (_disposed) return;
    _state = value;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _revision += 1;
    _retry = null;
    super.dispose();
  }
}

String _statusLabel(IncidentStatus status) => switch (status) {
  IncidentStatus.open => '未対応',
  IncidentStatus.investigating => '調査中',
  IncidentStatus.resolved => '解決済み',
};

extension<T> on List<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
