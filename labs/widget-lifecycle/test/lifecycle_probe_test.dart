// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:widget_lifecycle_lab/lifecycle_probe.dart';

void main() {
  testWidgets('lifecycleを順序どおり観測しdispose後は通知しない', (tester) async {
    final observed = <AppLifecycleState>[];
    await tester.pumpWidget(
      Directionality(
        textDirection: TextDirection.ltr,
        child: LifecycleProbe(onState: observed.add),
      ),
    );
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    expect(observed, [AppLifecycleState.inactive, AppLifecycleState.resumed]);

    await tester.pumpWidget(const SizedBox.shrink());
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    expect(observed, hasLength(2));
  });
}
