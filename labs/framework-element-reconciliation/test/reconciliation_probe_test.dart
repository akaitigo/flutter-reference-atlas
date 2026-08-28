// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:framework_element_reconciliation_lab/reconciliation_probe.dart';

void main() {
  testWidgets('Keyなしでは同じ位置のElementへStateを再利用する', (tester) async {
    await tester.pumpWidget(const ReconciliationProbe(keyed: false));
    expect(find.text('A:A'), findsOneWidget);
    expect(find.text('B:B'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('reverse')));
    await tester.pump();

    expect(find.text('B:A'), findsOneWidget);
    expect(find.text('A:B'), findsOneWidget);
  });

  testWidgets('LocalKeyは移動後も論理項目へStateを結び付ける', (tester) async {
    await tester.pumpWidget(const ReconciliationProbe(keyed: true));

    await tester.tap(find.byKey(const ValueKey('reverse')));
    await tester.pump();

    expect(find.text('B:B'), findsOneWidget);
    expect(find.text('A:A'), findsOneWidget);
    expect(find.text('B:A'), findsNothing);
    expect(find.text('A:B'), findsNothing);
  });
}
