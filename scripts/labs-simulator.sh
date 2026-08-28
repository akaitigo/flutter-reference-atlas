#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-doctor}"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
[[ -x "$flutter_bin" ]] || { echo "エラー: Flutter 3.47.1 SDKがありません: $sdk_root" >&2; exit 1; }

case "$action" in
  doctor)
    "$flutter_bin" doctor -v
    ios_ready=false
    android_ready=false
    if command -v xcrun >/dev/null 2>&1 && xcrun simctl list devices >/dev/null 2>&1; then
      ios_ready=true
    fi
    if command -v adb >/dev/null 2>&1 && command -v emulator >/dev/null 2>&1; then
      android_ready=true
    fi
    if [[ "$ios_ready" != true && "$android_ready" != true ]]; then
      echo "エラー: iOS SimulatorまたはAndroid EmulatorのToolchainがありません。" >&2
      exit 1
    fi
    ;;
  run)
    : "${FLUTTER_DEVICE_ID:?FLUTTER_DEVICE_IDへSimulatorまたはEmulator IDを指定してください}"
    cd "$repo_root/reference-systems/operations-workspace"
    "$flutter_bin" test integration_test/workspace_integration_test.dart -d "$FLUTTER_DEVICE_ID"
    ;;
  cleanup)
    echo "Flutter test runnerがApplication Processを終了します。外部Simulatorは停止しません。"
    ;;
  *)
    echo "使い方: scripts/labs-simulator.sh doctor|run|cleanup" >&2
    exit 2
    ;;
esac
