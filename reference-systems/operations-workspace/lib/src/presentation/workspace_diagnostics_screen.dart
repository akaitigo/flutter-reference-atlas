// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';

import '../domain/incident_input_policy.dart';
import '../observability/frame_performance_monitor.dart';
import '../platform/platform_capability_probe.dart';

class WorkspaceDiagnosticsScreen extends StatelessWidget {
  const WorkspaceDiagnosticsScreen({
    required this.performanceMonitor,
    required this.platformProbe,
    super.key,
  });

  final FramePerformanceMonitor performanceMonitor;
  final PlatformCapabilityProbe platformProbe;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('診断')),
      body: ListView(
        key: const Key('diagnostics-screen'),
        padding: const EdgeInsets.all(24),
        children: [
          Semantics(
            header: true,
            child: Text(
              '公開契約の観測',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
          ),
          const SizedBox(height: 24),
          const _SecurityContractCard(),
          const SizedBox(height: 16),
          _PerformanceCard(monitor: performanceMonitor),
          const SizedBox(height: 16),
          _PlatformCapabilityCard(probe: platformProbe),
        ],
      ),
    );
  }
}

class _PlatformCapabilityCard extends StatefulWidget {
  const _PlatformCapabilityCard({required this.probe});

  final PlatformCapabilityProbe probe;

  @override
  State<_PlatformCapabilityCard> createState() =>
      _PlatformCapabilityCardState();
}

class _PlatformCapabilityCardState extends State<_PlatformCapabilityCard> {
  PlatformCapabilitySnapshot? _snapshot;
  String? _failure;
  bool _loading = false;

  Future<void> _inspect() async {
    if (_loading) return;
    setState(() {
      _loading = true;
      _failure = null;
    });
    try {
      final snapshot = await widget.probe.inspect();
      if (!mounted) return;
      setState(() => _snapshot = snapshot);
    } on Object {
      if (!mounted) return;
      setState(() => _failure = 'Platform Runtimeへ接続できません。');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final snapshot = _snapshot;
    final subtitle = switch ((snapshot, _failure)) {
      (final value?, _) =>
        '${value.platform} ${value.osVersion} / SDK ${value.sdkInt} / '
            'codec ${value.codec} / Activity ${value.activityAttached ? 'attached' : 'detached'}',
      (_, final failure?) => failure,
      _ => 'MethodChannel Pluginの実Runtime情報を未取得です。',
    };
    return Card(
      key: const Key('platform-capability-card'),
      child: ListTile(
        leading: const Icon(Icons.developer_board),
        title: const Text('Platform Runtime'),
        subtitle: Text(subtitle),
        trailing: _loading
            ? const SizedBox.square(
                dimension: 24,
                child: CircularProgressIndicator(),
              )
            : FilledButton(
                key: const Key('probe-platform-button'),
                onPressed: _inspect,
                child: Text(snapshot == null ? '取得' : '再取得'),
              ),
      ),
    );
  }
}

class _SecurityContractCard extends StatelessWidget {
  const _SecurityContractCard();

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: ListTile(
        leading: Icon(Icons.security),
        title: Text('入力境界'),
        subtitle: Text(
          '件名は空白を正規化し、最大${IncidentTitlePolicy.maxRunes}文字に制限して、制御文字と双方向表示制御を拒否します。Repository例外の詳細はUIへ公開しません。',
        ),
      ),
    );
  }
}

class _PerformanceCard extends StatelessWidget {
  const _PerformanceCard({required this.monitor});

  final FramePerformanceMonitor monitor;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: monitor,
      builder: (context, _) {
        final snapshot = monitor.snapshot;
        final status = snapshot.sampleCount == 0
            ? '計測待ち'
            : snapshot.isWithinBudget
            ? '予算内'
            : '予算超過を観測';
        return Card(
          key: const Key('performance-card'),
          child: Semantics(
            liveRegion: true,
            label:
                'Frame性能 $status、${snapshot.sampleCount} sample、slow ${snapshot.slowFrameCount}',
            child: ListTile(
              leading: const Icon(Icons.speed),
              title: Text('Frame性能: $status'),
              subtitle: Text(
                'sample ${snapshot.sampleCount} / slow ${snapshot.slowFrameCount} / '
                'p95 ${snapshot.p95TotalSpan.inMicroseconds}µs / '
                'worst ${snapshot.worstTotalSpan.inMicroseconds}µs',
              ),
            ),
          ),
        );
      },
    );
  }
}
