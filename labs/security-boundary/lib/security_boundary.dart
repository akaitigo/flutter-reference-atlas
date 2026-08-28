// SPDX-License-Identifier: Apache-2.0

final class SecurityBoundary {
  SecurityBoundary({required Set<String> allowedHosts})
    : _allowedHosts = Set<String>.unmodifiable(allowedHosts);

  final Set<String> _allowedHosts;

  Uri validateRemoteUri(String value) {
    final uri = Uri.parse(value);
    if (uri.scheme != 'https' ||
        uri.userInfo.isNotEmpty ||
        !_allowedHosts.contains(uri.host)) {
      throw FormatException('remote URI is outside the allowlist');
    }
    return uri;
  }

  String validateRelativeAssetPath(String value) {
    final uri = Uri(path: value).normalizePath();
    if (uri.isAbsolute ||
        value.startsWith('/') ||
        uri.pathSegments.contains('..')) {
      throw const FormatException('asset path escapes its root');
    }
    return uri.path;
  }

  String redact(String message, Iterable<String> secrets) {
    var result = message;
    for (final secret in secrets.where((String value) => value.isNotEmpty)) {
      result = result.replaceAll(secret, '[REDACTED]');
    }
    return result;
  }

  int validatePlatformCounter(Object? value) {
    if (value is! int || value < 0 || value > 1000000) {
      throw const FormatException('platform response is outside the contract');
    }
    return value;
  }
}
