// SPDX-License-Identifier: Apache-2.0

import 'dart:js_interop';

String platformFamily() {
  const JSString marker = 'reference-atlas'.toJS;
  marker.toDart;
  return 'web';
}
