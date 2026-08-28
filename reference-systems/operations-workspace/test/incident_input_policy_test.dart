// SPDX-License-Identifier: Apache-2.0

import 'package:flutter_test/flutter_test.dart';
import 'package:operations_workspace/src/domain/incident_input_policy.dart';

void main() {
  test('空白を正規化して安全な件名を受理する', () {
    final result = IncidentTitlePolicy.validate('  API\n  遅延  ');

    expect(result.isAccepted, isTrue);
    expect(result.value, 'API 遅延');
  });

  test('制御文字と双方向表示制御を拒否する', () {
    expect(
      IncidentTitlePolicy.validate('表示\u202Etxt').error,
      '件名に利用できない制御文字が含まれています。',
    );
    expect(
      IncidentTitlePolicy.validate('null\u0000byte').error,
      '件名に利用できない制御文字が含まれています。',
    );
  });

  test('Unicode code point単位の上限を適用する', () {
    expect(
      IncidentTitlePolicy.validate(
        '障' * IncidentTitlePolicy.maxRunes,
      ).isAccepted,
      isTrue,
    );
    expect(
      IncidentTitlePolicy.validate(
        '障' * (IncidentTitlePolicy.maxRunes + 1),
      ).error,
      '件名は80文字以内で入力してください。',
    );
  });
}
