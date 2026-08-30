// SPDX-License-Identifier: Apache-2.0
import 'package:flutter/material.dart';

const variant = String.fromEnvironment('ATLAS_VARIANT');

void main() {
  const allowed = <String>{'javascript', 'release-js', 'wasm'};
  if (!allowed.contains(variant)) {
    throw StateError('Unsupported build web security variant: $variant');
  }
  runApp(const BuildWebSecurityApp());
}

class BuildWebSecurityApp extends StatelessWidget {
  const BuildWebSecurityApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          child: Semantics(
            label: 'build web security $variant PASS',
            excludeSemantics: true,
            child: const Text(
              'build.web\nsecurity\n$variant\nPASS',
              textAlign: TextAlign.center,
              textDirection: TextDirection.ltr,
            ),
          ),
        ),
      ),
    );
  }
}
