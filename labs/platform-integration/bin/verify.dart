// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:io';

import '../lib/source_contract_verifier.dart';

void main() {
  final labRoot = File.fromUri(Platform.script).parent.parent;
  final report = SourceContractVerifier(labRoot).verify();
  stdout.writeln(jsonEncode(report.toJson()));
  if (!report.passed) {
    exitCode = 1;
  }
}
