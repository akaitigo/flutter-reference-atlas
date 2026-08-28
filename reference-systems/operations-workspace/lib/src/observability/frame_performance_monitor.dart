// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

@immutable
class FramePerformanceSnapshot {
  const FramePerformanceSnapshot({
    this.sampleCount = 0,
    this.slowFrameCount = 0,
    this.p95TotalSpan = Duration.zero,
    this.worstTotalSpan = Duration.zero,
    this.frameBudget = const Duration(microseconds: 16667),
  });

  final int sampleCount;
  final int slowFrameCount;
  final Duration p95TotalSpan;
  final Duration worstTotalSpan;
  final Duration frameBudget;

  bool get isWithinBudget => slowFrameCount == 0;
}

/// Flutterの公開FrameTiming APIを、上限付きの観測値へ変換する。
class FramePerformanceMonitor extends ChangeNotifier {
  FramePerformanceMonitor({
    this.frameBudget = const Duration(microseconds: 16667),
    this.maxSamples = 120,
  }) : assert(maxSamples > 0);

  final Duration frameBudget;
  final int maxSamples;
  final List<Duration> _samples = [];
  bool _started = false;

  FramePerformanceSnapshot get snapshot => _summarize();

  void start() {
    if (_started) return;
    SchedulerBinding.instance.addTimingsCallback(recordFrameTimings);
    _started = true;
  }

  void stop() {
    if (!_started) return;
    SchedulerBinding.instance.removeTimingsCallback(recordFrameTimings);
    _started = false;
  }

  @visibleForTesting
  bool get isStarted => _started;

  void recordFrameTimings(List<FrameTiming> timings) {
    for (final timing in timings) {
      recordTotalSpan(timing.totalSpan);
    }
  }

  /// Rendererに依存しないUnit Testと外部計測Adapter用の公開入力境界。
  void recordTotalSpan(Duration duration) {
    _samples.add(duration);
    if (_samples.length > maxSamples) _samples.removeAt(0);
    notifyListeners();
  }

  FramePerformanceSnapshot _summarize() {
    if (_samples.isEmpty) {
      return FramePerformanceSnapshot(frameBudget: frameBudget);
    }
    final sorted = [..._samples]..sort();
    final p95Index = ((sorted.length - 1) * 0.95).ceil();
    return FramePerformanceSnapshot(
      sampleCount: sorted.length,
      slowFrameCount: sorted.where((sample) => sample > frameBudget).length,
      p95TotalSpan: sorted[p95Index],
      worstTotalSpan: sorted.last,
      frameBudget: frameBudget,
    );
  }

  @override
  void dispose() {
    stop();
    super.dispose();
  }
}
