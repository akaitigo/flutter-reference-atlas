// SPDX-License-Identifier: Apache-2.0

import 'dart:io';

String platformFamily() {
  if (Platform.isAndroid || Platform.isIOS) {
    return 'mobile';
  }
  if (Platform.isMacOS || Platform.isWindows || Platform.isLinux) {
    return 'desktop';
  }
  return 'unsupported';
}
