// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';

import '../domain/incident.dart';
import '../domain/incident_input_policy.dart';
import '../observability/frame_performance_monitor.dart';
import 'incident_status_chart.dart';
import 'workspace_controller.dart';
import 'workspace_diagnostics_screen.dart';

abstract final class WorkspaceRoutes {
  static const diagnostics = '/diagnostics';
}

class WorkspaceApp extends StatefulWidget {
  const WorkspaceApp({
    required this.repository,
    this.performanceMonitor,
    this.navigatorObservers = const [],
    super.key,
  });

  final IncidentRepository repository;
  final FramePerformanceMonitor? performanceMonitor;
  final List<NavigatorObserver> navigatorObservers;

  @override
  State<WorkspaceApp> createState() => _WorkspaceAppState();
}

class _WorkspaceAppState extends State<WorkspaceApp> {
  late final WorkspaceController controller;
  late final FramePerformanceMonitor performanceMonitor;
  late final bool _ownsPerformanceMonitor;

  @override
  void initState() {
    super.initState();
    controller = WorkspaceController(repository: widget.repository)..load();
    _ownsPerformanceMonitor = widget.performanceMonitor == null;
    performanceMonitor = widget.performanceMonitor ?? FramePerformanceMonitor();
    performanceMonitor.start();
  }

  @override
  void dispose() {
    controller.dispose();
    if (_ownsPerformanceMonitor) {
      performanceMonitor.dispose();
    } else {
      performanceMonitor.stop();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Operations Workspace',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff315da8)),
        useMaterial3: true,
      ),
      navigatorObservers: widget.navigatorObservers,
      onGenerateRoute: (settings) {
        if (settings.name == WorkspaceRoutes.diagnostics) {
          return MaterialPageRoute<void>(
            settings: settings,
            builder: (_) => WorkspaceDiagnosticsScreen(
              performanceMonitor: performanceMonitor,
            ),
          );
        }
        return null;
      },
      home: WorkspaceScreen(controller: controller),
    );
  }
}

class WorkspaceScreen extends StatelessWidget {
  const WorkspaceScreen({required this.controller, super.key});

  final WorkspaceController controller;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final state = controller.state;
        return Scaffold(
          appBar: AppBar(
            title: const Text('Operations Workspace'),
            actions: [
              IconButton(
                key: const Key('refresh-button'),
                tooltip: '再読み込み',
                onPressed: state.busy ? null : controller.load,
                icon: const Icon(Icons.refresh),
              ),
              IconButton(
                key: const Key('diagnostics-button'),
                tooltip: '診断を開く',
                onPressed: () => Navigator.of(
                  context,
                ).pushNamed(WorkspaceRoutes.diagnostics),
                icon: const Icon(Icons.monitor_heart_outlined),
              ),
            ],
          ),
          floatingActionButton: FloatingActionButton.extended(
            key: const Key('create-button'),
            onPressed: state.busy ? null : () => _showCreateDialog(context),
            icon: const Icon(Icons.add),
            label: const Text('追加'),
          ),
          body: Column(
            children: [
              if (state.saving)
                const LinearProgressIndicator(
                  key: Key('save-progress'),
                  semanticsLabel: '変更を保存中',
                ),
              if (state.failure case final failure?)
                MaterialBanner(
                  key: const Key('failure-banner'),
                  content: Semantics(
                    liveRegion: true,
                    child: Text(failure.message),
                  ),
                  actions: [
                    if (controller.canRetry)
                      TextButton(
                        key: const Key('retry-button'),
                        onPressed: state.busy ? null : controller.retry,
                        child: const Text('再試行'),
                      ),
                    TextButton(
                      onPressed: controller.dismissFailure,
                      child: const Text('閉じる'),
                    ),
                  ],
                ),
              if (state.announcement case final announcement?)
                Semantics(
                  key: const Key('status-announcement'),
                  liveRegion: true,
                  container: true,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 8,
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle_outline),
                        const SizedBox(width: 8),
                        Expanded(child: Text(announcement)),
                        IconButton(
                          tooltip: '通知を閉じる',
                          onPressed: controller.dismissAnnouncement,
                          icon: const Icon(Icons.close),
                        ),
                      ],
                    ),
                  ),
                ),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    if (constraints.maxWidth >= 800) {
                      return Row(
                        children: [
                          SizedBox(
                            width: 360,
                            child: IncidentList(controller: controller),
                          ),
                          const VerticalDivider(width: 1),
                          Expanded(
                            child: IncidentDetail(controller: controller),
                          ),
                        ],
                      );
                    }
                    return state.selected == null
                        ? IncidentList(controller: controller)
                        : IncidentDetail(
                            controller: controller,
                            showBack: true,
                          );
                  },
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _showCreateDialog(BuildContext context) async {
    var input = '';
    final title = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('インシデントを追加'),
        content: TextField(
          key: const Key('incident-title-field'),
          autofocus: true,
          decoration: const InputDecoration(labelText: '件名'),
          maxLength: IncidentTitlePolicy.maxRunes,
          onChanged: (value) => input = value,
          onSubmitted: (value) => Navigator.pop(context, value),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('キャンセル'),
          ),
          FilledButton(
            key: const Key('save-incident-button'),
            onPressed: () => Navigator.pop(context, input),
            child: const Text('保存'),
          ),
        ],
      ),
    );
    if (title != null) await controller.createIncident(title);
  }
}

class IncidentList extends StatelessWidget {
  const IncidentList({required this.controller, super.key});

  final WorkspaceController controller;

  @override
  Widget build(BuildContext context) {
    final state = controller.state;
    if (state.loading && state.incidents.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    return Semantics(
      label: 'インシデント一覧',
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: IncidentStatusChart(incidents: state.incidents),
          ),
          Expanded(
            child: ListView.builder(
              key: const Key('incident-list'),
              itemCount: state.incidents.length,
              itemBuilder: (context, index) {
                final incident = state.incidents[index];
                final selected = incident.id == state.selectedId;
                return MergeSemantics(
                  child: Semantics(
                    button: true,
                    selected: selected,
                    label:
                        '${incident.title}、状態 ${statusLabel(incident.status)}',
                    child: ListTile(
                      key: Key('incident-${incident.id}'),
                      selected: selected,
                      title: Text(incident.title),
                      subtitle: Text(statusLabel(incident.status)),
                      onTap: () => controller.select(incident.id),
                    ),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class IncidentDetail extends StatelessWidget {
  const IncidentDetail({
    required this.controller,
    this.showBack = false,
    super.key,
  });

  final WorkspaceController controller;
  final bool showBack;

  @override
  Widget build(BuildContext context) {
    final incident = controller.state.selected;
    if (incident == null) {
      return const Center(child: Text('インシデントを選択してください。'));
    }
    return FocusTraversalGroup(
      child: ListView(
        key: const Key('incident-detail'),
        padding: const EdgeInsets.all(24),
        children: [
          if (showBack)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: controller.clearSelection,
                icon: const Icon(Icons.arrow_back),
                label: const Text('一覧へ'),
              ),
            ),
          Semantics(
            header: true,
            child: Text(
              incident.title,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ),
          const SizedBox(height: 12),
          Semantics(
            label: '状態 ${statusLabel(incident.status)}',
            child: Chip(label: Text(statusLabel(incident.status))),
          ),
          const SizedBox(height: 16),
          Text(incident.description),
          const SizedBox(height: 24),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              key: const Key('advance-status-button'),
              onPressed:
                  incident.status == IncidentStatus.resolved ||
                      controller.state.busy
                  ? null
                  : controller.advanceSelected,
              child: const Text('次の状態へ'),
            ),
          ),
        ],
      ),
    );
  }
}
