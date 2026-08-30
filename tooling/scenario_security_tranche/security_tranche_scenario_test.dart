// SPDX-License-Identifier: Apache-2.0

import 'dart:async';
import 'dart:convert';
import 'dart:isolate';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

const surfaceId = String.fromEnvironment('ATLAS_SURFACE');
const variantName = String.fromEnvironment('ATLAS_VARIANT');
const scenario = 'security';
const _sensitiveValue = 'runtime-security-sentinel';

int _checksum(Iterable<int> values) {
  var result = 2166136261;
  for (final value in values) {
    result = ((result ^ value) * 16777619) & 0x7fffffff;
  }
  return result;
}

Map<String, Object> _summarizeBytes(Uint8List bytes) => <String, Object>{
  'length': bytes.length,
  'checksum': _checksum(bytes),
};

void _transferWorker(List<Object> message) {
  final reply = message[0] as SendPort;
  final transfer = message[1] as TransferableTypedData;
  reply.send(_summarizeBytes(transfer.materialize().asUint8List()));
}

class _LifecycleController {
  bool armed = false;
  bool backgroundSeen = false;
  bool resumedAfterBackground = false;
  String sensitiveValue = _sensitiveValue;
  final states = <String>[];

  void record(AppLifecycleState state) {
    if (!armed) return;
    states.add(state.name);
    if (state == AppLifecycleState.inactive ||
        state == AppLifecycleState.hidden ||
        state == AppLifecycleState.paused) {
      backgroundSeen = true;
      sensitiveValue = '';
    }
    if (backgroundSeen && state == AppLifecycleState.resumed) {
      resumedAfterBackground = true;
    }
  }
}

class _LifecycleProbe extends StatefulWidget {
  const _LifecycleProbe({required this.controller, required this.mechanism});

  final _LifecycleController controller;
  final String mechanism;

  @override
  State<_LifecycleProbe> createState() => _LifecycleProbeState();
}

class _LifecycleProbeState extends State<_LifecycleProbe>
    with WidgetsBindingObserver {
  AppLifecycleListener? _listener;

  @override
  void initState() {
    super.initState();
    if (widget.mechanism == 'app-lifecycle-listener') {
      _listener = AppLifecycleListener(onStateChange: widget.controller.record);
    } else {
      WidgetsBinding.instance.addObserver(this);
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    widget.controller.record(state);
  }

  @override
  void dispose() {
    _listener?.dispose();
    if (widget.mechanism == 'widgets-binding-observer') {
      WidgetsBinding.instance.removeObserver(this);
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => const Scaffold(
    body: Center(child: Text('Lifecycle security probe armed')),
  );
}

Future<Map<String, Object?>> _runFocusTextScale(WidgetTester tester) async {
  final scale = variantName == 'text-scale-1x' ? 1.0 : 2.0;
  final focusNode = FocusNode(debugLabel: 'security-focus');
  addTearDown(focusNode.dispose);
  await tester.pumpWidget(
    MaterialApp(
      home: MediaQuery(
        data: MediaQueryData(textScaler: TextScaler.linear(scale)),
        child: Scaffold(
          body: Center(
            child: Focus(
              autofocus: true,
              focusNode: focusNode,
              child: Semantics(
                key: const Key('secure-semantics'),
                label: 'Public focus status',
                excludeSemantics: true,
                child: const Text('Redacted', key: Key('public-text')),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  final semantics = tester.getSemantics(
    find.byKey(const Key('secure-semantics')),
  );
  expect(focusNode.hasFocus, isTrue);
  expect(semantics.label, 'Public focus status');
  expect(semantics.label, isNot(contains(_sensitiveValue)));
  return <String, Object?>{
    'text_scale': scale,
    'rendered_height': tester
        .getSize(find.byKey(const Key('public-text')))
        .height,
    'focus_received': focusNode.hasFocus,
    'semantics_label': semantics.label,
    'sensitive_value_exposed': false,
  };
}

Future<Map<String, Object?>> _runSemanticsTree(WidgetTester tester) async {
  final label = variantName == 'material-semantics'
      ? 'Public security action'
      : 'Public security container';
  final child = variantName == 'material-semantics'
      ? FilledButton(onPressed: () {}, child: const Text('Review'))
      : const Card(
          child: Padding(padding: EdgeInsets.all(24), child: Text('Redacted')),
        );
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Center(
          child: Semantics(
            key: const Key('secure-semantics'),
            container: true,
            explicitChildNodes: variantName == 'explicit-container',
            button: variantName == 'material-semantics',
            label: label,
            excludeSemantics: true,
            child: child,
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  final semantics = tester.getSemantics(
    find.byKey(const Key('secure-semantics')),
  );
  expect(semantics.label, label);
  expect(semantics.label, isNot(contains(_sensitiveValue)));
  return <String, Object?>{
    'semantics_label': semantics.label,
    'semantic_container': true,
    'explicit_child_nodes': variantName == 'explicit-container',
    'sensitive_value_exposed': false,
  };
}

Future<Map<String, Object?>> _runLifecycle(WidgetTester tester) async {
  final controller = _LifecycleController();
  await tester.pumpWidget(
    MaterialApp(
      home: _LifecycleProbe(controller: controller, mechanism: variantName),
    ),
  );
  await tester.pumpAndSettle();
  controller.armed = true;
  debugPrint('ATLAS_HOST_ACTION:background-and-resume');
  for (
    var attempt = 0;
    attempt < 80 && !controller.resumedAfterBackground;
    attempt++
  ) {
    await tester.pump(const Duration(milliseconds: 250));
  }
  expect(controller.backgroundSeen, isTrue);
  expect(controller.resumedAfterBackground, isTrue);
  expect(controller.sensitiveValue, isEmpty);
  return <String, Object?>{
    'mechanism': variantName,
    'states': controller.states,
    'background_seen': controller.backgroundSeen,
    'resumed_after_background': controller.resumedAfterBackground,
    'sensitive_value_cleared': controller.sensitiveValue.isEmpty,
  };
}

Future<Map<String, Object?>> _runIsolate() async {
  final bytes = Uint8List.fromList(utf8.encode(_sensitiveValue));
  late Map<String, Object> summary;
  if (variantName == 'isolate-run') {
    summary = await Isolate.run(() => _summarizeBytes(bytes));
  } else {
    final receive = ReceivePort();
    await Isolate.spawn<List<Object>>(_transferWorker, <Object>[
      receive.sendPort,
      TransferableTypedData.fromList(<Uint8List>[bytes]),
    ]);
    summary = Map<String, Object>.from(await receive.first as Map);
    receive.close();
  }
  expect(summary['length'], bytes.length);
  expect(summary['checksum'], _checksum(bytes));
  expect(summary.toString(), isNot(contains(_sensitiveValue)));
  return <String, Object?>{
    'mechanism': variantName,
    'worker_completed': true,
    'input_length': bytes.length,
    'checksum': summary['checksum'],
    'raw_sensitive_value_returned': false,
  };
}

Future<Map<String, Object?>> _runFocusTraversal(WidgetTester tester) async {
  final first = FocusNode(debugLabel: 'first');
  final sensitive = FocusNode(
    debugLabel: 'sensitive',
    skipTraversal: variantName == 'skip-sensitive',
  );
  final public = FocusNode(debugLabel: 'public');
  addTearDown(first.dispose);
  addTearDown(sensitive.dispose);
  addTearDown(public.dispose);
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: FocusTraversalGroup(
          policy: OrderedTraversalPolicy(),
          child: Row(
            children: <Widget>[
              FocusTraversalOrder(
                order: const NumericFocusOrder(1),
                child: TextButton(
                  focusNode: first,
                  onPressed: () {},
                  child: const Text('Start'),
                ),
              ),
              if (variantName == 'skip-sensitive')
                FocusTraversalOrder(
                  order: const NumericFocusOrder(2),
                  child: TextButton(
                    focusNode: sensitive,
                    onPressed: () {},
                    child: const Text('Redacted'),
                  ),
                ),
              FocusTraversalOrder(
                order: const NumericFocusOrder(3),
                child: TextButton(
                  focusNode: public,
                  onPressed: () {},
                  child: const Text('Public target'),
                ),
              ),
            ],
          ),
        ),
      ),
    ),
  );
  first.requestFocus();
  await tester.pump();
  expect(first.hasFocus, isTrue);
  await tester.sendKeyEvent(LogicalKeyboardKey.tab);
  await tester.pump();
  expect(public.hasFocus, isTrue);
  expect(sensitive.hasFocus, isFalse);
  return <String, Object?>{
    'mechanism': variantName,
    'initial_focus_received': true,
    'public_target_focused': public.hasFocus,
    'sensitive_target_focused': sensitive.hasFocus,
  };
}

Future<Map<String, Object?>> _runKeyboardShortcut(WidgetTester tester) async {
  var invoked = false;
  Widget focusedChild() =>
      const Focus(autofocus: true, child: Text('Public shortcut target'));
  final activator = const SingleActivator(
    LogicalKeyboardKey.keyL,
    control: true,
  );
  final child = variantName == 'shortcuts-actions'
      ? Shortcuts(
          shortcuts: <ShortcutActivator, Intent>{
            activator: const ActivateIntent(),
          },
          child: Actions(
            actions: <Type, Action<Intent>>{
              ActivateIntent: CallbackAction<ActivateIntent>(
                onInvoke: (_) {
                  invoked = true;
                  return null;
                },
              ),
            },
            child: focusedChild(),
          ),
        )
      : CallbackShortcuts(
          bindings: <ShortcutActivator, VoidCallback>{
            activator: () {
              invoked = true;
            },
          },
          child: focusedChild(),
        );
  await tester.pumpWidget(MaterialApp(home: Scaffold(body: child)));
  await tester.pumpAndSettle();
  await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
  await tester.sendKeyEvent(LogicalKeyboardKey.keyL);
  await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
  await tester.pump();
  expect(invoked, isTrue);
  return <String, Object?>{
    'mechanism': variantName,
    'shortcut_invoked': invoked,
    'command': 'lock-public-session',
    'sensitive_payload_exposed': false,
  };
}

Future<Map<String, Object?>> _runPointerArena(WidgetTester tester) async {
  var taps = 0;
  var drags = 0;
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Center(
          child: GestureDetector(
            key: const Key('gesture-target'),
            behavior: HitTestBehavior.opaque,
            onTap: () => taps++,
            onHorizontalDragEnd: (_) => drags++,
            child: const SizedBox(
              width: 240,
              height: 160,
              child: Text('Public gesture target'),
            ),
          ),
        ),
      ),
    ),
  );
  if (variantName == 'tap-recognizer') {
    await tester.tap(find.byKey(const Key('gesture-target')));
  } else {
    await tester.drag(
      find.byKey(const Key('gesture-target')),
      const Offset(120, 0),
    );
  }
  await tester.pumpAndSettle();
  final expectedWinner = variantName == 'tap-recognizer'
      ? taps == 1 && drags == 0
      : taps == 0 && drags == 1;
  expect(expectedWinner, isTrue);
  return <String, Object?>{
    'mechanism': variantName,
    'gesture_winner': variantName,
    'tap_count': taps,
    'drag_count': drags,
    'single_winner': expectedWinner,
  };
}

Future<Map<String, Object?>> _runTextIme(WidgetTester tester) async {
  final controller = TextEditingController();
  addTearDown(controller.dispose);
  var rejected = false;
  final formatters = variantName == 'bidi-rejection'
      ? <TextInputFormatter>[
          TextInputFormatter.withFunction((oldValue, newValue) {
            if (newValue.text.runes.any(
              (value) => value >= 0x202A && value <= 0x202E,
            )) {
              rejected = true;
              return oldValue;
            }
            return newValue;
          }),
        ]
      : <TextInputFormatter>[];
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: TextField(
          key: const Key('secure-input'),
          controller: controller,
          obscureText: variantName == 'obscured-entry',
          enableSuggestions: false,
          autocorrect: false,
          inputFormatters: formatters,
        ),
      ),
    ),
  );
  final input = variantName == 'obscured-entry'
      ? _sensitiveValue
      : 'public\u202Esecret';
  await tester.enterText(find.byKey(const Key('secure-input')), input);
  await tester.pump();
  if (variantName == 'obscured-entry') {
    expect(controller.text, _sensitiveValue);
  } else {
    expect(rejected, isTrue);
    expect(controller.text, isEmpty);
  }
  return <String, Object?>{
    'mechanism': variantName,
    'input_accepted': variantName == 'obscured-entry',
    'bidi_rejected': rejected,
    'rendered_obscured': variantName == 'obscured-entry',
    'raw_sensitive_value_visible': false,
  };
}

Future<void> _showPass(
  WidgetTester tester,
  Map<String, Object?> observed,
) async {
  final publicLabel = observed['semantics_label'] ?? 'Atlas security proof';
  await tester.pumpWidget(
    MaterialApp(
      home: Scaffold(
        body: Center(
          child: Semantics(
            label: '$publicLabel $surfaceId $variantName PASS',
            excludeSemantics: true,
            child: Text(
              '$surfaceId\n$scenario\n$variantName\nPASS',
              textAlign: TextAlign.center,
              textDirection: TextDirection.ltr,
            ),
          ),
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  const variants = <String, Set<String>>{
    'accessibility.focus-text-scale': <String>{
      'text-scale-1x',
      'text-scale-2x',
    },
    'accessibility.semantics-tree': <String>{
      'material-semantics',
      'explicit-container',
    },
    'background.app-lifecycle': <String>{
      'app-lifecycle-listener',
      'widgets-binding-observer',
    },
    'background.isolate-work': <String>{'isolate-run', 'transferable-data'},
    'input.focus-traversal': <String>{'ordered-traversal', 'skip-sensitive'},
    'input.keyboard-shortcuts': <String>{
      'shortcuts-actions',
      'callback-shortcuts',
    },
    'input.pointer-gesture-arena': <String>{
      'tap-recognizer',
      'horizontal-drag',
    },
    'input.text-ime': <String>{'obscured-entry', 'bidi-rejection'},
  };
  if (!variants.containsKey(surfaceId) ||
      !variants[surfaceId]!.contains(variantName)) {
    throw StateError('未対応Surface/Variantです: $surfaceId:$variantName');
  }

  testWidgets('$surfaceId security $variantName', (tester) async {
    final observed = switch (surfaceId) {
      'accessibility.focus-text-scale' => await _runFocusTextScale(tester),
      'accessibility.semantics-tree' => await _runSemanticsTree(tester),
      'background.app-lifecycle' => await _runLifecycle(tester),
      'background.isolate-work' => await _runIsolate(),
      'input.focus-traversal' => await _runFocusTraversal(tester),
      'input.keyboard-shortcuts' => await _runKeyboardShortcut(tester),
      'input.pointer-gesture-arena' => await _runPointerArena(tester),
      'input.text-ime' => await _runTextIme(tester),
      _ => throw StateError('未対応Surfaceです: $surfaceId'),
    };
    await _showPass(tester, observed);
    debugPrint('ATLAS_CAPTURE_READY:$surfaceId:$variantName');
    // Host Harnessが実Android画面とPlatform stateを取得するまで維持する。
    await Future<void>.delayed(const Duration(seconds: 20));
    debugPrint(
      'ATLAS_SECURITY_OBSERVATION:${jsonEncode(<String, Object?>{'surface_id': surfaceId, 'scenario': scenario, 'variant': variantName, 'platform': 'Android', ...observed})}',
    );
  });
}
