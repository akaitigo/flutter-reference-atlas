// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/widgets.dart';

class ReconciliationProbe extends StatefulWidget {
  const ReconciliationProbe({required this.keyed, super.key});

  final bool keyed;

  @override
  State<ReconciliationProbe> createState() => _ReconciliationProbeState();
}

class _ReconciliationProbeState extends State<ReconciliationProbe> {
  var _labels = const ['A', 'B'];

  void reverse() {
    setState(() {
      _labels = _labels.reversed.toList(growable: false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.ltr,
      child: Column(
        children: [
          GestureDetector(
            key: const ValueKey('reverse'),
            onTap: reverse,
            child: const Text('reverse'),
          ),
          for (final label in _labels)
            IdentityTile(
              key: widget.keyed ? ValueKey(label) : null,
              label: label,
            ),
        ],
      ),
    );
  }
}

class IdentityTile extends StatefulWidget {
  const IdentityTile({required this.label, super.key});

  final String label;

  @override
  State<IdentityTile> createState() => _IdentityTileState();
}

class _IdentityTileState extends State<IdentityTile> {
  late final String mountedFor = widget.label;

  @override
  Widget build(BuildContext context) => Text('${widget.label}:$mountedFor');
}
