// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

final class VerificationIssue {
  const VerificationIssue({
    required this.code,
    required this.location,
    required this.message,
  });

  final String code;
  final String location;
  final String message;

  Map<String, Object> toJson() => {
    'code': code,
    'location': location,
    'message': message,
  };
}

final class VerificationReport {
  const VerificationReport({
    required this.labId,
    required this.contractsChecked,
    required this.sourceAssertionsChecked,
    required this.runtimeEvidence,
    required this.issues,
  });

  final String labId;
  final int contractsChecked;
  final int sourceAssertionsChecked;
  final Map<String, String> runtimeEvidence;
  final List<VerificationIssue> issues;

  bool get passed => issues.isEmpty;

  Map<String, Object> toJson() => {
    'schema_version': 1,
    'lab_id': labId,
    'verdict': passed ? 'pass' : 'fail',
    'contracts_checked': contractsChecked,
    'source_assertions_checked': sourceAssertionsChecked,
    'evidence': {
      'source_contract': passed ? 'pass' : 'fail',
      'runtime_evidence': runtimeEvidence,
    },
    'issues': issues.map((issue) => issue.toJson()).toList(growable: false),
  };
}

final class SourceContractVerifier {
  const SourceContractVerifier(this.labRoot);

  final Directory labRoot;

  VerificationReport verify() {
    final issues = <VerificationIssue>[];
    final runtimeEvidence = <String, String>{};
    var contractCount = 0;
    var assertionCount = 0;
    var labId = 'lab.platform-integration-source-contract';
    final manifest = File('${labRoot.path}/contracts/platform_contracts.json');

    Object? decoded;
    try {
      decoded = jsonDecode(manifest.readAsStringSync());
    } on Object catch (error) {
      issues.add(
        VerificationIssue(
          code: 'manifest-unreadable',
          location: _relativeLocation(manifest.path),
          message: 'Contract Manifestを読めません: $error',
        ),
      );
      return VerificationReport(
        labId: labId,
        contractsChecked: 0,
        sourceAssertionsChecked: 0,
        runtimeEvidence: const {},
        issues: issues,
      );
    }

    if (decoded is! Map<String, Object?>) {
      issues.add(
        const VerificationIssue(
          code: 'manifest-shape',
          location: 'contracts/platform_contracts.json',
          message: 'Top-levelはJSON Objectである必要があります。',
        ),
      );
      return VerificationReport(
        labId: labId,
        contractsChecked: 0,
        sourceAssertionsChecked: 0,
        runtimeEvidence: const {},
        issues: issues,
      );
    }

    if (decoded['lab_id'] case final String value) {
      labId = value;
    } else {
      issues.add(
        const VerificationIssue(
          code: 'missing-lab-id',
          location: 'contracts/platform_contracts.json',
          message: 'lab_idが必要です。',
        ),
      );
    }

    final contractsValue = decoded['contracts'];
    if (contractsValue is! List<Object?>) {
      issues.add(
        const VerificationIssue(
          code: 'contracts-shape',
          location: 'contracts/platform_contracts.json',
          message: 'contractsはArrayである必要があります。',
        ),
      );
      return VerificationReport(
        labId: labId,
        contractsChecked: 0,
        sourceAssertionsChecked: 0,
        runtimeEvidence: const {},
        issues: issues,
      );
    }

    final seenIds = <String>{};
    for (final contractValue in contractsValue) {
      if (contractValue is! Map<String, Object?>) {
        issues.add(
          const VerificationIssue(
            code: 'contract-shape',
            location: 'contracts',
            message: '各ContractはJSON Objectである必要があります。',
          ),
        );
        continue;
      }
      contractCount += 1;
      final idValue = contractValue['id'];
      final id = idValue is String ? idValue : 'contract[$contractCount]';
      if (idValue is! String || idValue.isEmpty) {
        issues.add(
          VerificationIssue(
            code: 'missing-contract-id',
            location: id,
            message: '空でないContract IDが必要です。',
          ),
        );
      } else if (!seenIds.add(id)) {
        issues.add(
          VerificationIssue(
            code: 'duplicate-contract-id',
            location: id,
            message: 'Contract IDが重複しています。',
          ),
        );
      }
      if (contractValue['scope'] != 'source_contract') {
        issues.add(
          VerificationIssue(
            code: 'invalid-contract-scope',
            location: id,
            message: 'このLabのContract scopeはsource_contractに限定します。',
          ),
        );
      }

      final runtimeValue = contractValue['runtime_evidence'];
      if (runtimeValue is! Map<String, Object?>) {
        issues.add(
          VerificationIssue(
            code: 'missing-runtime-boundary',
            location: id,
            message: 'runtime_evidence境界が必要です。',
          ),
        );
      } else {
        final status = runtimeValue['status'];
        if (status is! String ||
            const {'not_collected', 'blocked'}.contains(status) == false) {
          issues.add(
            VerificationIssue(
              code: 'invalid-runtime-status',
              location: id,
              message: 'Native未実行Labではruntime statusをpassにできません。',
            ),
          );
        } else {
          runtimeEvidence[id] = status;
        }
        final requirements = _stringList(
          runtimeValue['requires'],
          location: '$id.runtime_evidence.requires',
          issues: issues,
        );
        if (requirements.isEmpty) {
          issues.add(
            VerificationIssue(
              code: 'missing-runtime-requirements',
              location: id,
              message: 'Runtime Evidenceに必要な外部条件を列挙してください。',
            ),
          );
        }
      }

      final checksValue = contractValue['checks'];
      if (checksValue is! List<Object?> || checksValue.isEmpty) {
        issues.add(
          VerificationIssue(
            code: 'missing-source-checks',
            location: id,
            message: '1件以上のSource checkが必要です。',
          ),
        );
      } else {
        for (final checkValue in checksValue) {
          if (checkValue is! Map<String, Object?>) {
            issues.add(
              VerificationIssue(
                code: 'source-check-shape',
                location: id,
                message: 'Source checkはJSON Objectである必要があります。',
              ),
            );
            continue;
          }
          final result = _verifySourceCheck(id, checkValue, issues);
          assertionCount += result;
        }
      }

      final tokensValue = contractValue['shared_tokens'];
      if (tokensValue is List<Object?>) {
        for (final tokenValue in tokensValue) {
          if (tokenValue is! Map<String, Object?>) {
            issues.add(
              VerificationIssue(
                code: 'shared-token-shape',
                location: id,
                message: 'shared_tokensの各要素はJSON Objectが必要です。',
              ),
            );
            continue;
          }
          assertionCount += _verifySharedToken(id, tokenValue, issues);
        }
      }
    }

    return VerificationReport(
      labId: labId,
      contractsChecked: contractCount,
      sourceAssertionsChecked: assertionCount,
      runtimeEvidence: Map.unmodifiable(runtimeEvidence),
      issues: List.unmodifiable(issues),
    );
  }

  int _verifySourceCheck(
    String contractId,
    Map<String, Object?> check,
    List<VerificationIssue> issues,
  ) {
    final pathValue = check['file'];
    if (pathValue is! String || !isSafeRelativePath(pathValue)) {
      issues.add(
        VerificationIssue(
          code: 'unsafe-source-path',
          location: contractId,
          message: 'Lab root配下の安全な相対Pathが必要です: $pathValue',
        ),
      );
      return 0;
    }
    final source = File('${labRoot.path}/$pathValue');
    if (!source.existsSync()) {
      issues.add(
        VerificationIssue(
          code: 'missing-source-file',
          location: pathValue,
          message: 'Contractが参照するSource fileがありません。',
        ),
      );
      return 0;
    }
    final content = source.readAsStringSync();
    final required = _stringList(
      check['contains'],
      location: '$contractId:$pathValue.contains',
      issues: issues,
    );
    final forbidden = _stringList(
      check['not_contains'],
      location: '$contractId:$pathValue.not_contains',
      issues: issues,
      optional: true,
    );
    for (final token in required) {
      if (!content.contains(token)) {
        issues.add(
          VerificationIssue(
            code: 'missing-required-token',
            location: pathValue,
            message: '必要な宣言が見つかりません: $token',
          ),
        );
      }
    }
    for (final token in forbidden) {
      if (content.contains(token)) {
        issues.add(
          VerificationIssue(
            code: 'forbidden-token',
            location: pathValue,
            message: 'Platform境界外の宣言が含まれています: $token',
          ),
        );
      }
    }
    return required.length + forbidden.length;
  }

  int _verifySharedToken(
    String contractId,
    Map<String, Object?> token,
    List<VerificationIssue> issues,
  ) {
    final name = token['name'];
    final value = token['value'];
    final files = _stringList(
      token['files'],
      location: '$contractId.shared_tokens',
      issues: issues,
    );
    if (name is! String || value is! String || value.isEmpty || files.isEmpty) {
      issues.add(
        VerificationIssue(
          code: 'invalid-shared-token',
          location: contractId,
          message: 'shared tokenにはname、value、filesが必要です。',
        ),
      );
      return 0;
    }
    for (final path in files) {
      if (!isSafeRelativePath(path)) {
        issues.add(
          VerificationIssue(
            code: 'unsafe-source-path',
            location: '$contractId.$name',
            message: 'Lab root配下の安全な相対Pathが必要です: $path',
          ),
        );
        continue;
      }
      final source = File('${labRoot.path}/$path');
      if (!source.existsSync()) {
        issues.add(
          VerificationIssue(
            code: 'missing-source-file',
            location: path,
            message: '共有識別子を検査するSource fileがありません。',
          ),
        );
      } else if (!source.readAsStringSync().contains(value)) {
        issues.add(
          VerificationIssue(
            code: 'shared-token-mismatch',
            location: path,
            message: '$nameの共有値が一致しません: $value',
          ),
        );
      }
    }
    return files.length;
  }

  static bool isSafeRelativePath(String path) {
    if (path.isEmpty || path.startsWith('/') || path.contains('\\')) {
      return false;
    }
    final segments = path.split('/');
    return segments.every(
      (segment) => segment.isNotEmpty && segment != '.' && segment != '..',
    );
  }

  static List<String> _stringList(
    Object? value, {
    required String location,
    required List<VerificationIssue> issues,
    bool optional = false,
  }) {
    if (value == null && optional) return const [];
    if (value is! List<Object?> || value.any((item) => item is! String)) {
      issues.add(
        VerificationIssue(
          code: 'string-list-shape',
          location: location,
          message: 'String Arrayが必要です。',
        ),
      );
      return const [];
    }
    return value.cast<String>();
  }

  String _relativeLocation(String path) {
    final prefix = '${labRoot.path}/';
    return path.startsWith(prefix) ? path.substring(prefix.length) : path;
  }
}
