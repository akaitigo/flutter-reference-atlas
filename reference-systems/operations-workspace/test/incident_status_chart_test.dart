// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/domain/incident.dart';
import 'package:operations_workspace/src/presentation/incident_status_chart.dart';

void main() {
  testWidgets('CustomPainterの状態集計をSemanticsでも公開する', (tester) async {
    final semantics = tester.ensureSemantics();
    await tester.pumpWidget(
      MaterialApp(
        home: IncidentStatusChart(
          incidents: [
            Incident(
              id: 'open',
              title: 'Open',
              description: 'Open incident',
              status: IncidentStatus.open,
              updatedAt: DateTime.utc(2026, 8, 20),
            ),
            Incident(
              id: 'resolved',
              title: 'Resolved',
              description: 'Resolved incident',
              status: IncidentStatus.resolved,
              updatedAt: DateTime.utc(2026, 8, 19),
            ),
          ],
        ),
      ),
    );

    final node = tester.getSemantics(
      find.byKey(const Key('incident-status-chart')),
    );
    expect(node.label, contains('未対応 1件'));
    expect(node.label, contains('調査中 0件'));
    expect(node.label, contains('解決済み 1件'));
    expect(find.byType(CustomPaint), findsWidgets);
    semantics.dispose();
  });

  test('Painterは集計値の変化だけで再描画する', () {
    final colors = {
      for (final status in IncidentStatus.values) status: Colors.blue,
    };
    final original = IncidentStatusPainter(
      counts: const {
        IncidentStatus.open: 1,
        IncidentStatus.investigating: 0,
        IncidentStatus.resolved: 0,
      },
      colors: colors,
    );
    final same = IncidentStatusPainter(
      counts: const {
        IncidentStatus.open: 1,
        IncidentStatus.investigating: 0,
        IncidentStatus.resolved: 0,
      },
      colors: colors,
    );
    final changed = IncidentStatusPainter(
      counts: const {
        IncidentStatus.open: 0,
        IncidentStatus.investigating: 1,
        IncidentStatus.resolved: 0,
      },
      colors: colors,
    );

    expect(same.shouldRepaint(original), isFalse);
    expect(changed.shouldRepaint(original), isTrue);
  });
}
