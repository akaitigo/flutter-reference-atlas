// SPDX-License-Identifier: Apache-2.0

import 'package:flutter/material.dart';

import 'src/data/in_memory_incident_repository.dart';
import 'src/presentation/workspace_app.dart';

void main() {
  runApp(WorkspaceApp(repository: InMemoryIncidentRepository.seeded()));
}
