// SPDX-License-Identifier: Apache-2.0

import 'dart:convert';
import 'dart:ffi';
import 'dart:io';

typedef _NativeAdd = Int32 Function(Int32 left, Int32 right);
typedef _DartAdd = int Function(int left, int right);

void main() {
  final labRoot = File.fromUri(Platform.script).parent.parent;
  final temporaryRoot = Directory.systemTemp.createTempSync(
    'platform-integration-ffi-',
  );
  final libraryFile = File('${temporaryRoot.path}/libatlas_math.dylib');
  Map<String, Object> report;
  var passed = false;

  try {
    if (!Platform.isMacOS) {
      throw UnsupportedError('このRuntime verifierはmacOS専用です。');
    }
    final architecture = Process.runSync('uname', const ['-m']);
    if (architecture.exitCode != 0 ||
        architecture.stdout.toString().trim() != 'arm64') {
      throw UnsupportedError('このRuntime verifierはmacOS arm64専用です。');
    }

    final compile = Process.runSync('/usr/bin/clang', [
      '-std=c11',
      '-Wall',
      '-Wextra',
      '-Werror',
      '-dynamiclib',
      '-arch',
      'arm64',
      '-I',
      '${labRoot.path}/fixtures/ffi/include',
      '${labRoot.path}/fixtures/ffi/src/atlas_math.c',
      '-o',
      libraryFile.path,
    ]);
    if (compile.exitCode != 0) {
      throw StateError('clang buildに失敗しました: ${compile.stderr}');
    }
    if (!libraryFile.existsSync()) {
      throw StateError('一時dylibが生成されませんでした。');
    }

    final library = DynamicLibrary.open(libraryFile.path);
    int actual;
    try {
      final atlasAdd = library.lookupFunction<_NativeAdd, _DartAdd>(
        'atlas_add',
      );
      actual = atlasAdd(19, 23);
    } finally {
      library.close();
    }
    if (actual != 42) {
      throw StateError('atlas_add(19, 23)の結果が42ではありません: $actual');
    }

    passed = true;
    report = {
      'schema_version': 1,
      'lab_id': 'lab.platform-integration-source-contract',
      'evidence_layer': 'runtime_evidence',
      'integration': 'dart-ffi',
      'target': 'macos-arm64',
      'dart_version': Platform.version.split(' ').first,
      'compiler': 'apple-clang-17',
      'operation': 'atlas_add(19, 23)',
      'actual': actual,
    };
  } on Object catch (error) {
    report = {
      'schema_version': 1,
      'lab_id': 'lab.platform-integration-source-contract',
      'evidence_layer': 'runtime_evidence',
      'integration': 'dart-ffi',
      'target': 'macos-arm64',
      'error': error.toString(),
    };
  } finally {
    if (temporaryRoot.existsSync()) {
      temporaryRoot.deleteSync(recursive: true);
    }
  }

  report['cleanup'] = temporaryRoot.existsSync() ? 'fail' : 'pass';
  report['verdict'] = passed && report['cleanup'] == 'pass' ? 'pass' : 'fail';
  stdout.writeln(jsonEncode(report));
  if (report['verdict'] != 'pass') {
    exitCode = 1;
  }
}
