// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';

import 'package:security_boundary/security_boundary.dart';

void main() {
  final boundary = SecurityBoundary(
    allowedHosts: <String>{'api.example.invalid'},
  );
  final allowed = boundary.validateRemoteUri(
    'https://api.example.invalid/v1/incidents',
  );
  if (allowed.scheme != 'https') {
    throw StateError('HTTPS allowlist check failed');
  }
  _expectRejected(
    () => boundary.validateRemoteUri('http://api.example.invalid/v1'),
  );
  _expectRejected(
    () => boundary.validateRemoteUri('https://attacker.invalid/v1'),
  );
  _expectRejected(
    () => boundary.validateRemoteUri('https://token@api.example.invalid/v1'),
  );
  _expectRejected(
    () => boundary.validateRelativeAssetPath('../../private/key'),
  );
  if (boundary.validateRelativeAssetPath('assets/config.json') !=
      'assets/config.json') {
    throw StateError('safe asset path changed');
  }
  const secret = 'atlas-secret-value';
  final redacted = boundary.redact('authorization=$secret', <String>[secret]);
  if (redacted.contains(secret) || !redacted.contains('[REDACTED]')) {
    throw StateError('secret redaction failed');
  }
  if (boundary.validatePlatformCounter(42) != 42) {
    throw StateError('valid platform response changed');
  }
  _expectRejected(() => boundary.validatePlatformCounter(-1));
  _expectRejected(() => boundary.validatePlatformCounter('42'));

  print(
    jsonEncode(<String, Object?>{
      'schema_version': 1,
      'lab_id': 'lab.security-boundary',
      'verdict': 'pass',
      'checks': <String, bool>{
        'https_allowlist': true,
        'credential_uri_rejected': true,
        'path_traversal_rejected': true,
        'secret_redacted': true,
        'platform_response_validated': true,
      },
    }),
  );
}

void _expectRejected(void Function() action) {
  try {
    action();
  } on FormatException {
    return;
  }
  throw StateError('unsafe input was accepted');
}
