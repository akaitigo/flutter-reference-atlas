// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/foundation.dart';

@immutable
class IncidentTitleValidation {
  const IncidentTitleValidation.accepted(this.value) : error = null;

  const IncidentTitleValidation.rejected(this.error) : value = null;

  final String? value;
  final String? error;

  bool get isAccepted => value != null;
}

/// 利用者入力をDomainへ渡す前に適用する、小さく監査可能な境界Policy。
abstract final class IncidentTitlePolicy {
  static const int maxRunes = 80;

  static final RegExp _forbiddenControls = RegExp(
    r'[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\u202A-\u202E\u2066-\u2069]',
  );

  static IncidentTitleValidation validate(String input) {
    final normalized = input.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (normalized.isEmpty) {
      return const IncidentTitleValidation.rejected('件名を入力してください。');
    }
    if (_forbiddenControls.hasMatch(normalized)) {
      return const IncidentTitleValidation.rejected('件名に利用できない制御文字が含まれています。');
    }
    if (normalized.runes.length > maxRunes) {
      return const IncidentTitleValidation.rejected('件名は80文字以内で入力してください。');
    }
    return IncidentTitleValidation.accepted(normalized);
  }
}
