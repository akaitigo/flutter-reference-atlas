// SPDX-License-Identifier: Apache-2.0
import 'package:flutter/material.dart';

const variant = String.fromEnvironment('ATLAS_VARIANT');

void main() {
  const allowed = <String>{'debug-apk-install', 'release-apk'};
  if (!allowed.contains(variant)) {
    throw StateError('Unsupported build security variant: $variant');
  }
  runApp(const BuildSecurityApp());
}

class BuildSecurityApp extends StatelessWidget {
  const BuildSecurityApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          child: Semantics(
            label: 'build android security $variant PASS',
            excludeSemantics: true,
            child: const Text(
              'build.android\nsecurity\n$variant\nPASS',
              textAlign: TextAlign.center,
              textDirection: TextDirection.ltr,
            ),
          ),
        ),
      ),
    );
  }
}
