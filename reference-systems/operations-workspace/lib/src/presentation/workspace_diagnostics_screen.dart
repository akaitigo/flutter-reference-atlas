// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';

import '../domain/incident_input_policy.dart';
import '../observability/frame_performance_monitor.dart';

class WorkspaceDiagnosticsScreen extends StatelessWidget {
  const WorkspaceDiagnosticsScreen({
    required this.performanceMonitor,
    super.key,
  });

  final FramePerformanceMonitor performanceMonitor;

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
        ],
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
