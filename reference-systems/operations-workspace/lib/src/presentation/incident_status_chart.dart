// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../domain/incident.dart';

class IncidentStatusChart extends StatelessWidget {
  const IncidentStatusChart({required this.incidents, super.key});

  final List<Incident> incidents;

  @override
  Widget build(BuildContext context) {
    final counts = {
      for (final status in IncidentStatus.values)
        status: incidents.where((incident) => incident.status == status).length,
    };
    final label = IncidentStatus.values
        .map((status) => '${statusLabel(status)} ${counts[status]}件')
        .join('、');
    final colors = {
      IncidentStatus.open: Theme.of(context).colorScheme.error,
      IncidentStatus.investigating: Theme.of(context).colorScheme.tertiary,
      IncidentStatus.resolved: Theme.of(context).colorScheme.primary,
    };
    return Semantics(
      key: const Key('incident-status-chart'),
      container: true,
      label: '状態別件数。$label',
      image: true,
      child: ExcludeSemantics(
        child: SizedBox(
          height: 56,
          child: CustomPaint(
            painter: IncidentStatusPainter(counts: counts, colors: colors),
            child: const SizedBox.expand(),
          ),
        ),
      ),
    );
  }
}

class IncidentStatusPainter extends CustomPainter {
  IncidentStatusPainter({required this.counts, required this.colors});

  final Map<IncidentStatus, int> counts;
  final Map<IncidentStatus, Color> colors;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Paint()..color = const Color(0x1F808080);
    final radius = Radius.circular(size.height / 2);
    final bounds = Offset.zero & size;
    canvas.drawRRect(RRect.fromRectAndRadius(bounds, radius), background);

    final total = counts.values.fold<int>(0, (sum, count) => sum + count);
    if (total == 0 || size.isEmpty) return;

    var left = 0.0;
    for (final status in IncidentStatus.values) {
      final count = counts[status] ?? 0;
      if (count == 0) continue;
      final width = size.width * count / total;
      final segment = Rect.fromLTWH(left, 0, width, size.height);
      canvas.save();
      canvas.clipRRect(RRect.fromRectAndRadius(bounds, radius));
      canvas.drawRect(
        segment,
        Paint()..color = colors[status] ?? const Color(0xff808080),
      );
      canvas.restore();
      left += width;
    }
  }

  @override
  bool shouldRepaint(covariant IncidentStatusPainter oldDelegate) {
    return !mapEquals(oldDelegate.counts, counts) ||
        !mapEquals(oldDelegate.colors, colors);
  }
}

String statusLabel(IncidentStatus status) => switch (status) {
  IncidentStatus.open => '未対応',
  IncidentStatus.investigating => '調査中',
  IncidentStatus.resolved => '解決済み',
};
