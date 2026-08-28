// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:framework_rendering_pipeline_lab/pipeline_probe.dart';

void main() {
  testWidgets('Constraintでsizeを決めlayout後にpaintする', (tester) async {
    final trace = PipelineTrace();
    await tester.pumpWidget(
      Center(
        child: SizedBox(
          width: 50,
          height: 40,
          child: PipelineProbe(extent: 100, paintRevision: 0, trace: trace),
        ),
      ),
    );

    expect(tester.getSize(find.byType(PipelineProbe)), const Size(50, 40));
    expect(trace.events, ['layout', 'paint:0']);
  });

  testWidgets('paint変更はlayoutを再実行しない', (tester) async {
    final trace = PipelineTrace();
    final paintRevision = ValueNotifier(0);
    addTearDown(paintRevision.dispose);
    await tester.pumpWidget(
      ValueListenableBuilder<int>(
        valueListenable: paintRevision,
        builder: (context, revision, child) =>
            PipelineProbe(extent: 20, paintRevision: revision, trace: trace),
      ),
    );
    trace.clear();

    paintRevision.value = 1;
    await tester.pump();

    expect(trace.events, ['paint:1']);
  });

  testWidgets('layout変更はlayoutとpaintを順に再実行する', (tester) async {
    final trace = PipelineTrace();
    final extent = ValueNotifier(20.0);
    addTearDown(extent.dispose);
    await tester.pumpWidget(
      Align(
        alignment: Alignment.topLeft,
        child: ValueListenableBuilder<double>(
          valueListenable: extent,
          builder: (context, value, child) =>
              PipelineProbe(extent: value, paintRevision: 0, trace: trace),
        ),
      ),
    );
    trace.clear();

    extent.value = 40;
    await tester.pump();

    expect(trace.events, ['layout', 'paint:0']);
    expect(tester.getSize(find.byType(PipelineProbe)), const Size(40, 40));
  });
}
