// SPDX-License-Identifier: Apache-2.0

export 'platform_service_stub.dart'
    if (dart.library.io) 'platform_service_io.dart'
    if (dart.library.js_interop) 'platform_service_web.dart';
