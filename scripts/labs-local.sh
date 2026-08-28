#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dart run "$repo_root/labs/offline-conflict-resolution/bin/verify.dart"
(
  cd "$repo_root/labs/widget-lifecycle"
  flutter test
)
(
  cd "$repo_root/reference-systems/operations-workspace"
  flutter test
)
