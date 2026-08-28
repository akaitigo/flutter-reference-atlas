// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';

import '../domain/incident.dart';
import 'workspace_controller.dart';

class WorkspaceApp extends StatefulWidget {
  const WorkspaceApp({required this.repository, super.key});

  final IncidentRepository repository;

  @override
  State<WorkspaceApp> createState() => _WorkspaceAppState();
}

class _WorkspaceAppState extends State<WorkspaceApp> {
  late final WorkspaceController controller;

  @override
  void initState() {
    super.initState();
    controller = WorkspaceController(repository: widget.repository)..load();
  }

  @override
  void dispose() {
    controller.dispose();
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
                onPressed: state.loading ? null : controller.load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          floatingActionButton: FloatingActionButton.extended(
            key: const Key('create-button'),
            onPressed: () => _showCreateDialog(context),
            icon: const Icon(Icons.add),
            label: const Text('追加'),
          ),
          body: Column(
            children: [
              if (state.message case final message?)
                MaterialBanner(
                  content: Text(message),
                  actions: [
                    TextButton(
                      onPressed: controller.load,
                      child: const Text('再試行'),
                    ),
                  ],
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
      child: ListView.builder(
        key: const Key('incident-list'),
        itemCount: state.incidents.length,
        itemBuilder: (context, index) {
          final incident = state.incidents[index];
          return ListTile(
            selected: incident.id == state.selectedId,
            title: Text(incident.title),
            subtitle: Text(_statusLabel(incident.status)),
            onTap: () => controller.select(incident.id),
          );
        },
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
          Text(
            incident.title,
            style: Theme.of(context).textTheme.headlineMedium,
          ),
          const SizedBox(height: 12),
          Semantics(
            label: '状態 ${_statusLabel(incident.status)}',
            child: Chip(label: Text(_statusLabel(incident.status))),
          ),
          const SizedBox(height: 16),
          Text(incident.description),
          const SizedBox(height: 24),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton(
              key: const Key('advance-status-button'),
              onPressed: incident.status == IncidentStatus.resolved
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

String _statusLabel(IncidentStatus status) => switch (status) {
  IncidentStatus.open => '未対応',
  IncidentStatus.investigating => '調査中',
  IncidentStatus.resolved => '解決済み',
};
