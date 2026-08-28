#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
dart_bin="$sdk_root/bin/dart"
[[ -x "$flutter_bin" && -x "$dart_bin" ]] || { echo "エラー: Flutter 3.47.1 SDKがありません: $sdk_root" >&2; exit 1; }
"$dart_bin" run "$repo_root/labs/offline-conflict-resolution/bin/verify.dart"
(
  cd "$repo_root/labs/widget-lifecycle"
  "$flutter_bin" test
)
(
  cd "$repo_root/reference-systems/operations-workspace"
  "$flutter_bin" test
)
