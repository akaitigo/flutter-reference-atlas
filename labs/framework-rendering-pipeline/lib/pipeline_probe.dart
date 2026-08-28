// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/widgets.dart';

class PipelineTrace {
  final events = <String>[];

  void clear() => events.clear();
}

class PipelineProbe extends LeafRenderObjectWidget {
  const PipelineProbe({
    required this.extent,
    required this.paintRevision,
    required this.trace,
    super.key,
  });

  final double extent;
  final int paintRevision;
  final PipelineTrace trace;

  @override
  RenderPipelineProbe createRenderObject(BuildContext context) {
    return RenderPipelineProbe(
      extent: extent,
      paintRevision: paintRevision,
      trace: trace,
    );
  }

  @override
  void updateRenderObject(
    BuildContext context,
    RenderPipelineProbe renderObject,
  ) {
    renderObject
      ..trace = trace
      ..extent = extent
      ..paintRevision = paintRevision;
  }
}

class RenderPipelineProbe extends RenderBox {
  RenderPipelineProbe({
    required double extent,
    required int paintRevision,
    required PipelineTrace trace,
  }) : _extent = extent,
       _paintRevision = paintRevision,
       _trace = trace;

  double _extent;
  int _paintRevision;
  PipelineTrace _trace;

  set extent(double value) {
    if (_extent == value) return;
    _extent = value;
    markNeedsLayout();
  }

  set paintRevision(int value) {
    if (_paintRevision == value) return;
    _paintRevision = value;
    markNeedsPaint();
  }

  set trace(PipelineTrace value) {
    if (identical(_trace, value)) return;
    _trace = value;
    markNeedsPaint();
  }

  @override
  void performLayout() {
    _trace.events.add('layout');
    size = constraints.constrain(Size.square(_extent));
  }

  @override
  void paint(PaintingContext context, Offset offset) {
    _trace.events.add('paint:$_paintRevision');
    context.canvas.drawRect(
      offset & size,
      Paint()..color = const Color(0xFF1565C0),
    );
  }
}
