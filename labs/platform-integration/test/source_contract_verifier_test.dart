// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

import '../lib/source_contract_verifier.dart';

void main() {
  final labRoot = File.fromUri(Platform.script).parent.parent;
  final completed = <String>[];

  final baseline = SourceContractVerifier(labRoot).verify();
  _expect(baseline.passed, '同梱Source Contractはpassする');
  _expect(baseline.contractsChecked == 7, '7種類のContractを検証する');
  _expect(
    baseline.runtimeEvidence.values.every(
      (status) => status == 'not_collected' || status == 'blocked',
    ),
    'Native runtime evidenceをpassへ昇格しない',
  );
  completed.add('baseline-source-contract');

  _expect(
    SourceContractVerifier.isSafeRelativePath(
      'fixtures/platform_channel/lib/device_bridge.dart',
    ),
    'Lab内の相対Pathを許可する',
  );
  _expect(
    !SourceContractVerifier.isSafeRelativePath('../outside.dart'),
    'Lab外へのPath traversalを拒否する',
  );
  completed.add('path-boundary');

  final temporaryRoot = Directory.systemTemp.createTempSync(
    'platform-integration-contract-test-',
  );
  try {
    _copyTree(
      Directory('${labRoot.path}/contracts'),
      temporaryRoot,
      'contracts',
    );
    _copyTree(Directory('${labRoot.path}/fixtures'), temporaryRoot, 'fixtures');
    final dartBridge = File(
      '${temporaryRoot.path}/fixtures/platform_channel/lib/device_bridge.dart',
    );
    dartBridge.writeAsStringSync(
      dartBridge.readAsStringSync().replaceAll(
        'getPlatformVersion',
        'getBrokenVersion',
      ),
    );
    final mutated = SourceContractVerifier(temporaryRoot).verify();
    _expect(!mutated.passed, '共有Method名の改変を検出する');
    _expect(
      mutated.issues.any(
        (issue) =>
            issue.code == 'missing-required-token' ||
            issue.code == 'shared-token-mismatch',
      ),
      '改変理由をSource Contract違反として報告する',
    );
    completed.add('mutation-detection');
  } finally {
    temporaryRoot.deleteSync(recursive: true);
  }

  stdout.writeln(
    jsonEncode({
      'schema_version': 1,
      'lab_id': 'lab.platform-integration-source-contract',
      'verdict': 'pass',
      'tests': completed,
    }),
  );
}

void _copyTree(Directory source, Directory destinationRoot, String name) {
  final destination = Directory('${destinationRoot.path}/$name')..createSync();
  for (final entity in source.listSync(recursive: true)) {
    final relative = entity.path.substring(source.path.length + 1);
    final target = '${destination.path}/$relative';
    if (entity is Directory) {
      Directory(target).createSync(recursive: true);
    } else if (entity is File) {
      File(target).parent.createSync(recursive: true);
      entity.copySync(target);
    }
  }
}

void _expect(bool condition, String message) {
  if (!condition) throw StateError(message);
}
