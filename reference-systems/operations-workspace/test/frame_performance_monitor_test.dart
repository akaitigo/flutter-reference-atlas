// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/observability/frame_performance_monitor.dart';

void main() {
  test('Frame budget超過とp95を公開Snapshotへ集約する', () {
    final monitor = FramePerformanceMonitor(
      frameBudget: const Duration(milliseconds: 16),
      maxSamples: 5,
    );
    addTearDown(monitor.dispose);

    for (final milliseconds in [8, 10, 12, 18, 20]) {
      monitor.recordTotalSpan(Duration(milliseconds: milliseconds));
    }

    expect(monitor.snapshot.sampleCount, 5);
    expect(monitor.snapshot.slowFrameCount, 2);
    expect(monitor.snapshot.p95TotalSpan, const Duration(milliseconds: 20));
    expect(monitor.snapshot.worstTotalSpan, const Duration(milliseconds: 20));
    expect(monitor.snapshot.isWithinBudget, isFalse);
  });

  test('Sample保持数を上限で制限する', () {
    final monitor = FramePerformanceMonitor(maxSamples: 2);
    addTearDown(monitor.dispose);

    monitor.recordTotalSpan(const Duration(milliseconds: 30));
    monitor.recordTotalSpan(const Duration(milliseconds: 10));
    monitor.recordTotalSpan(const Duration(milliseconds: 12));

    expect(monitor.snapshot.sampleCount, 2);
    expect(monitor.snapshot.worstTotalSpan, const Duration(milliseconds: 12));
  });
}
