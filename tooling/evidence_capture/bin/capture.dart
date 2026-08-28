// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

Future<void> main(List<String> arguments) async {
  final options = _parseOptions(arguments);
  final root = Directory.current.absolute;
  final sdkRoot = Directory(options.sdkPath).absolute;
  final flutter = '${sdkRoot.path}/bin/flutter';
  final dart = '${sdkRoot.path}/bin/dart';
  if (!File(flutter).existsSync() || !File(dart).existsSync()) {
    stderr.writeln('Flutter SDKが見つかりません: ${sdkRoot.path}');
    exitCode = 2;
    return;
  }

  final environment = <String, String>{
    ...Platform.environment,
    'PATH': '${sdkRoot.path}/bin:${Platform.environment['PATH'] ?? ''}',
    'FLUTTER_SUPPRESS_ANALYTICS': 'true',
    'CI': 'true',
  };
  final webOutput = await Directory.systemTemp.createTemp('flutter-atlas-web-');
  final commands = <_CommandSpec>[
    _CommandSpec('sdk-version', flutter, const <String>[
      '--version',
      '--machine',
    ], root.path),
    _CommandSpec('sdk-doctor', flutter, const <String>[
      'doctor',
      '-v',
    ], root.path),
    _CommandSpec('surface-inventory-check', 'python3', <String>[
      'tooling/surface_inventory/generate.py',
      '--sdk-root',
      sdkRoot.path,
      '--output',
      'baseline/public-surface-inventory.json',
      '--check',
    ], root.path),
    _CommandSpec('surface-inventory-tests', 'python3', const <String>[
      '-m',
      'unittest',
      'tooling/surface_inventory/test_generate.py',
    ], root.path),
    _CommandSpec('operations-drill', dart, const <String>[
      'run',
      'labs/operations-drill/bin/verify.dart',
    ], root.path),
    _CommandSpec('security-boundary', dart, const <String>[
      'run',
      'labs/security-boundary/bin/verify.dart',
    ], root.path),
    _CommandSpec('platform-source-contract', dart, const <String>[
      'run',
      'labs/platform-integration/bin/verify.dart',
    ], root.path),
    _CommandSpec('platform-analyze', dart, const <String>[
      'analyze',
      'labs/platform-integration',
    ], root.path),
    _CommandSpec('platform-source-mutation-test', dart, const <String>[
      'run',
      'labs/platform-integration/test/source_contract_verifier_test.dart',
    ], root.path),
    _CommandSpec('platform-ffi-runtime', dart, const <String>[
      'run',
      'labs/platform-integration/bin/verify_ffi_runtime.dart',
    ], root.path),
    _CommandSpec('framework-reconciliation-test', flutter, const <String>[
      'test',
    ], '${root.path}/labs/framework-element-reconciliation'),
    _CommandSpec('framework-rendering-test', flutter, const <String>[
      'test',
    ], '${root.path}/labs/framework-rendering-pipeline'),
    _CommandSpec('widget-lifecycle-test', flutter, const <String>[
      'test',
    ], '${root.path}/labs/widget-lifecycle'),
    _CommandSpec('product-analyze', flutter, const <String>[
      'analyze',
    ], '${root.path}/reference-systems/operations-workspace'),
    _CommandSpec('product-test', flutter, const <String>[
      'test',
    ], '${root.path}/reference-systems/operations-workspace'),
    _CommandSpec('web-release-build', flutter, <String>[
      'build',
      'web',
      '--release',
      '--output=${webOutput.path}',
    ], '${root.path}/reference-systems/operations-workspace'),
  ];

  final results = <Map<String, Object?>>[];
  var passed = true;
  try {
    for (final command in commands) {
      final stopwatch = Stopwatch()..start();
      final result = await Process.run(
        command.executable,
        command.arguments,
        workingDirectory: command.workingDirectory,
        environment: environment,
      );
      stopwatch.stop();
      String sanitize(String value) => _sanitize(
        value,
        root: root.path,
        sdkRoot: sdkRoot.path,
        temporaryOutput: webOutput.path,
      );
      final record = <String, Object?>{
        'id': command.id,
        'command': <String>[
          sanitize(command.executable),
          ...command.arguments.map(sanitize),
        ],
        'working_directory': _relative(root.path, command.workingDirectory),
        'exit_code': result.exitCode,
        'elapsed_milliseconds': stopwatch.elapsedMilliseconds,
        'stdout': _tail(sanitize(result.stdout.toString())),
        'stderr': _tail(sanitize(result.stderr.toString())),
      };
      results.add(record);
      if (result.exitCode != 0) {
        passed = false;
        break;
      }
    }

    final versionRecord = results.cast<Map<String, Object?>>().firstWhere(
      (Map<String, Object?> record) => record['id'] == 'sdk-version',
    );
    final version = _decodeVersion(versionRecord['stdout'] as String);
    if (version['frameworkVersion'] != '3.47.1' ||
        version['dartSdkVersion']?.toString().startsWith('3.13.1') != true ||
        version['frameworkRevision'] !=
            '6655482ec06e547f90abf8ae7590466f4415978d') {
      passed = false;
    }

    final webMetrics = _directoryMetrics(webOutput);
    final report = <String, Object?>{
      'schema_version': 1,
      'harness_id': 'formal-local-closure',
      'created_at': DateTime.now().toUtc().toIso8601String(),
      'verdict': passed ? 'pass' : 'fail',
      'sdk': <String, Object?>{
        'flutter': version['frameworkVersion'],
        'framework_revision': version['frameworkRevision'],
        'engine_revision': version['engineRevision'],
        'dart': version['dartSdkVersion'],
        'devtools': version['devToolsVersion'],
      },
      'web_build': webMetrics,
      'results': results,
    };
    final output = File(options.outputPath)..parent.createSync(recursive: true);
    output.writeAsStringSync(
      '${const JsonEncoder.withIndent('  ').convert(report)}\n',
      flush: true,
    );
    stdout.writeln(
      jsonEncode(<String, Object?>{
        'verdict': report['verdict'],
        'output': output.path,
        'commands': results.length,
      }),
    );
    if (!passed) exitCode = 1;
  } finally {
    if (webOutput.existsSync()) webOutput.deleteSync(recursive: true);
  }
}

Map<String, Object?> _decodeVersion(String source) {
  try {
    final decoded = jsonDecode(source);
    return decoded is Map<String, Object?> ? decoded : <String, Object?>{};
  } on FormatException {
    return <String, Object?>{};
  }
}

Map<String, Object> _directoryMetrics(Directory directory) {
  var files = 0;
  var bytes = 0;
  if (directory.existsSync()) {
    for (final entity in directory.listSync(recursive: true)) {
      if (entity is File) {
        files += 1;
        bytes += entity.lengthSync();
      }
    }
  }
  return <String, Object>{'files': files, 'bytes': bytes};
}

String _relative(String root, String path) {
  if (path == root) return '.';
  return path.startsWith('$root/') ? path.substring(root.length + 1) : path;
}

String _tail(String value) {
  const maximum = 4000;
  final trimmed = value.trim();
  return trimmed.length <= maximum
      ? trimmed
      : trimmed.substring(trimmed.length - maximum);
}

String _sanitize(
  String value, {
  required String root,
  required String sdkRoot,
  required String temporaryOutput,
}) {
  return value
      .replaceAll(temporaryOutput, r'$WEB_OUTPUT')
      .replaceAll(sdkRoot, r'$FORMAL_SDK')
      .replaceAll(root, r'$ATLAS_ROOT');
}

_Options _parseOptions(List<String> arguments) {
  String? sdk;
  String? output;
  for (var index = 0; index < arguments.length; index += 1) {
    switch (arguments[index]) {
      case '--sdk':
        sdk = arguments[++index];
      case '--output':
        output = arguments[++index];
    }
  }
  if (sdk == null || output == null) {
    throw const FormatException(
      'usage: capture.dart --sdk <flutter-root> --output <report.json>',
    );
  }
  return _Options(sdkPath: sdk, outputPath: output);
}

final class _Options {
  const _Options({required this.sdkPath, required this.outputPath});

  final String sdkPath;
  final String outputPath;
}

final class _CommandSpec {
  const _CommandSpec(
    this.id,
    this.executable,
    this.arguments,
    this.workingDirectory,
  );

  final String id;
  final String executable;
  final List<String> arguments;
  final String workingDirectory;
}
