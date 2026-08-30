#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
android_sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-${HOME}/Library/Android/sdk}}"
flutter_bin="$sdk_root/bin/flutter"
adb_bin="$android_sdk/platform-tools/adb"
emulator_bin="$android_sdk/emulator/emulator"
avd_name="${FLUTTER_ATLAS_ANDROID_AVD:-medium_phone}"
output_dir="$repo_root/.tools/definitive-android"
workspace="$repo_root/reference-systems/operations-workspace"
artifact="$repo_root/evidence/artifacts/definitive-android-method-channel-report.json"
device_id="${FLUTTER_ATLAS_DEVICE_ID:-}"
started_emulator=false

die() {
  echo "エラー: $*" >&2
  exit 1
}

resolve_emulator() {
  local candidate=""
  if [[ -n "$device_id" ]] && "$adb_bin" -s "$device_id" get-state >/dev/null 2>&1; then
    return 0
  fi
  candidate="$("$adb_bin" devices | awk 'NR > 1 && $2 == "device" && $1 ~ /^emulator-/ { print $1; exit }')"
  if [[ -n "$candidate" ]]; then
    device_id="$candidate"
    return 0
  fi
  "$emulator_bin" -list-avds | grep -Fxq "$avd_name" || die "固定AVDがありません: $avd_name"
  mkdir -p "$output_dir"
  "$emulator_bin" "@$avd_name" -no-snapshot-save -no-boot-anim >"$output_dir/emulator.log" 2>&1 &
  started_emulator=true
  "$adb_bin" wait-for-device
  for _ in $(seq 1 120); do
    candidate="$("$adb_bin" devices | awk 'NR > 1 && $2 == "device" && $1 ~ /^emulator-/ { print $1; exit }')"
    if [[ -n "$candidate" && "$("$adb_bin" -s "$candidate" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; then
      device_id="$candidate"
      return 0
    fi
    sleep 1
  done
  die "Android Emulatorのbootが120秒以内に完了しませんでした。"
}

cleanup() {
  if [[ -n "$device_id" ]]; then
    "$adb_bin" -s "$device_id" shell am force-stop dev.akaitigo.atlas.operations_workspace >/dev/null 2>&1 || true
    if [[ "$started_emulator" == true ]]; then
      "$adb_bin" -s "$device_id" emu kill >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup EXIT

[[ -x "$flutter_bin" ]] || die "固定Flutter SDKがありません: $sdk_root"
[[ -x "$adb_bin" ]] || die "adbがありません: $adb_bin"
[[ -x "$emulator_bin" ]] || die "Android Emulatorがありません: $emulator_bin"
mkdir -p "$output_dir" "$repo_root/.tools/xdg-config"
export ANDROID_HOME="$android_sdk"
export ANDROID_SDK_ROOT="$android_sdk"
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

resolve_emulator
[[ "$("$adb_bin" -s "$device_id" shell getprop ro.kernel.qemu | tr -d '\r')" == "1" ]] || die "$device_id はEmulatorではありません。"
[[ "$("$adb_bin" -s "$device_id" shell getprop ro.build.version.sdk | tr -d '\r')" == "36" ]] || die "Android API 36が必要です。"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
(
  cd "$workspace"
  "$flutter_bin" test integration_test/workspace_integration_test.dart -d "$device_id" --no-pub
) 2>&1 | tee "$output_dir/integration-test.log"
exit_code=${PIPESTATUS[0]}
set -e
finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 "$repo_root/tooling/definitive_android/report.py" \
  --output "$artifact" \
  --log "$output_dir/integration-test.log" \
  --evidence-log "$repo_root/evidence/artifacts/definitive-android-method-channel.log" \
  --test-file "$workspace/integration_test/workspace_integration_test.dart" \
  --dart-plugin "$workspace/packages/atlas_runtime_probe/lib/atlas_runtime_probe.dart" \
  --android-plugin "$workspace/packages/atlas_runtime_probe/android/src/main/kotlin/dev/akaitigo/atlas/runtime_probe/AtlasRuntimeProbePlugin.kt" \
  --pubspec-lock "$workspace/pubspec.lock" \
  --device-id "$device_id" \
  --api-level 36 \
  --started-at "$started_at" \
  --finished-at "$finished_at" \
  --exit-code "$exit_code"

[[ "$exit_code" == "0" ]] || die "Android Definitive Runtime Testが失敗しました。"
echo "Android MethodChannel Runtime Evidenceを生成しました: $artifact"
