#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
action="${1:-doctor}"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
reporter="$repo_root/tooling/simulator_profile/report.py"
output_dir="${FLUTTER_ATLAS_SIMULATOR_OUTPUT_DIR:-$repo_root/.tools/simulator}"
workspace="$repo_root/reference-systems/operations-workspace"
application_id="dev.akaitigo.atlas.operations_workspace"
expected_android_api="${FLUTTER_ATLAS_ANDROID_API_LEVEL:-36}"

die() {
  echo "エラー: $*" >&2
  exit 1
}

prepend_path() {
  local candidate="$1"
  if [[ -d "$candidate" ]]; then
    PATH="$candidate:$PATH"
  fi
}

find_android_sdk() {
  local candidate=""
  local local_properties="$workspace/android/local.properties"
  for candidate in "${ANDROID_HOME:-}" "${ANDROID_SDK_ROOT:-}"; do
    if [[ -n "$candidate" && -x "$candidate/platform-tools/adb" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  if [[ -f "$local_properties" ]]; then
    candidate="$(sed -n 's/^sdk\.dir=//p' "$local_properties" | head -n 1 | sed 's/\\:/:/g; s/\\\\/\\/g')"
    if [[ -n "$candidate" && -x "$candidate/platform-tools/adb" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  fi
  candidate="${HOME}/Library/Android/sdk"
  if [[ -x "$candidate/platform-tools/adb" ]]; then
    printf '%s\n' "$candidate"
    return 0
  fi
  return 1
}

configure_toolchains() {
  [[ -x "$flutter_bin" ]] || die "Flutter 3.47.1 SDKがありません: $sdk_root"
  [[ -x "$reporter" ]] || die "Simulator report generatorがありません: $reporter"
  prepend_path "$sdk_root/bin"

  android_sdk="$(find_android_sdk || true)"
  if [[ -n "$android_sdk" ]]; then
    export ANDROID_HOME="$android_sdk"
    export ANDROID_SDK_ROOT="$android_sdk"
    prepend_path "$android_sdk/cmdline-tools/latest/bin"
    prepend_path "$android_sdk/emulator"
    prepend_path "$android_sdk/platform-tools"
  fi

  if [[ -z "${JAVA_HOME:-}" && -d "/Applications/Android Studio.app/Contents/jbr/Contents/Home" ]]; then
    export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
  fi
  export PATH
}

resolve_device_id() {
  local requested="${FLUTTER_ATLAS_DEVICE_ID:-${FLUTTER_DEVICE_ID:-}}"
  local android_devices=""
  local ios_devices=""
  if [[ -n "$requested" ]]; then
    printf '%s\n' "$requested"
    return 0
  fi

  if command -v adb >/dev/null 2>&1; then
    android_devices="$(adb devices | awk 'NR > 1 && $2 == "device" && $1 ~ /^emulator-/ { print $1 }')"
  fi
  if [[ -n "$android_devices" && "$(printf '%s\n' "$android_devices" | wc -l | tr -d ' ')" == "1" ]]; then
    printf '%s\n' "$android_devices"
    return 0
  fi

  if command -v xcrun >/dev/null 2>&1; then
    ios_devices="$(xcrun simctl list devices booted 2>/dev/null | sed -nE 's/.*\(([0-9A-F-]{36})\) \(Booted\).*/\1/p')"
  fi
  if [[ -n "$ios_devices" && "$(printf '%s\n' "$ios_devices" | wc -l | tr -d ' ')" == "1" ]]; then
    printf '%s\n' "$ios_devices"
    return 0
  fi

  die "起動済みEmulator/Simulatorを一意に選べません。FLUTTER_ATLAS_DEVICE_IDを指定してください。"
}

android_property() {
  local device_id="$1"
  local property="$2"
  adb -s "$device_id" shell getprop "$property" 2>/dev/null | tr -d '\r'
}

detect_runner_kind() {
  local device_id="$1"
  if command -v adb >/dev/null 2>&1 && adb -s "$device_id" get-state >/dev/null 2>&1; then
    if [[ "$(android_property "$device_id" ro.kernel.qemu)" != "1" ]]; then
      die "$device_id はAndroid実機です。Simulator Profileでは実機Evidenceを生成しません。"
    fi
    printf '%s\n' "android-emulator"
    return 0
  fi
  if command -v xcrun >/dev/null 2>&1 && xcrun simctl list devices booted | grep -Fq "$device_id"; then
    printf '%s\n' "ios-simulator"
    return 0
  fi
  die "$device_id は起動済みAndroid EmulatorまたはiOS Simulatorとして確認できません。"
}

write_inventory() {
  local device_id="$1"
  local runner_kind="$2"
  local version_path="$output_dir/flutter-version.json"
  local devices_path="$output_dir/flutter-devices.json"
  local doctor_path="$output_dir/flutter-doctor.log"
  local inventory_path="$output_dir/runtime-inventory.json"
  local os_version=""
  local api_level=""
  local model=""
  local runtime_name=""
  local architecture=""

  mkdir -p "$output_dir" "$repo_root/.tools/xdg-config"
  env XDG_CONFIG_HOME="$repo_root/.tools/xdg-config" "$flutter_bin" --version --machine > "$version_path"
  env XDG_CONFIG_HOME="$repo_root/.tools/xdg-config" "$flutter_bin" devices --machine > "$devices_path"
  env XDG_CONFIG_HOME="$repo_root/.tools/xdg-config" "$flutter_bin" doctor -v > "$doctor_path" 2>&1 || true

  if [[ "$runner_kind" == "android-emulator" ]]; then
    [[ -n "$android_sdk" ]] || die "Android SDKを検出できません。ANDROID_HOMEまたはANDROID_SDK_ROOTを設定してください。"
    [[ -x "$android_sdk/emulator/emulator" ]] || die "Android Emulator binaryがありません: $android_sdk/emulator/emulator"
    [[ "$(android_property "$device_id" sys.boot_completed)" == "1" ]] || die "$device_id のboot完了を確認できません。"
    api_level="$(android_property "$device_id" ro.build.version.sdk)"
    [[ "$api_level" == "$expected_android_api" ]] || die "$device_id のAPI levelは$api_levelです。固定値$expected_android_apiが必要です。"
    os_version="$(android_property "$device_id" ro.build.version.release)"
    model="$(android_property "$device_id" ro.product.model)"
    runtime_name="$(android_property "$device_id" ro.boot.qemu.avd_name)"
    architecture="$(android_property "$device_id" ro.product.cpu.abi)"
  else
    xcrun simctl list devices booted | grep -Fq "$device_id" || die "$device_id はBooted iOS Simulatorではありません。"
    runtime_name="$(xcrun simctl list devices booted | grep -F "$device_id" | head -n 1 | sed -E 's/^[[:space:]]*//')"
    model="$runtime_name"
    architecture="$(uname -m)"
    os_version="$(xcrun simctl getenv "$device_id" SIMULATOR_RUNTIME_VERSION 2>/dev/null || true)"
  fi

  python3 "$reporter" inventory \
    --output "$inventory_path" \
    --flutter-version-file "$version_path" \
    --flutter-devices-file "$devices_path" \
    --doctor-log "$doctor_path" \
    --sdk-root "$sdk_root" \
    --repo-root "$repo_root" \
    --runner-kind "$runner_kind" \
    --device-id "$device_id" \
    --runtime-name "$runtime_name" \
    --model "$model" \
    --os-version "$os_version" \
    --api-level "$api_level" \
    --architecture "$architecture" \
    --expected-flutter "3.47.1" \
    --expected-dart "3.13.1" \
    --expected-devtools "2.60.0"
  echo "Simulator実行Inventoryを生成しました: $inventory_path"
}

run_lab() {
  local device_id="$1"
  local runner_kind="$2"
  local inventory_path="$output_dir/runtime-inventory.json"
  local log_path="$output_dir/integration-test.log"
  local report_path="$output_dir/integration-test-report.json"
  local started_at=""
  local finished_at=""
  local exit_code=0
  local command_text=""

  write_inventory "$device_id" "$runner_kind"
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  command_text=".tools/flutter-3.47.1/flutter/bin/flutter test integration_test/workspace_integration_test.dart -d $device_id --no-pub"
  set +e
  (
    cd "$workspace"
    env XDG_CONFIG_HOME="$repo_root/.tools/xdg-config" "$flutter_bin" test integration_test/workspace_integration_test.dart -d "$device_id" --no-pub
  ) 2>&1 | tee "$log_path"
  exit_code=${PIPESTATUS[0]}
  set -e
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  python3 "$reporter" report \
    --output "$report_path" \
    --inventory "$inventory_path" \
    --log "$log_path" \
    --test-file "$workspace/integration_test/workspace_integration_test.dart" \
    --pubspec-lock "$workspace/pubspec.lock" \
    --command "$command_text" \
    --started-at "$started_at" \
    --finished-at "$finished_at" \
    --exit-code "$exit_code"
  echo "Simulator Integration Test Reportを生成しました: $report_path"
  [[ "$exit_code" == "0" ]] || die "Integration Testが失敗しました。ReportとLogを確認してください。"
}

cleanup_lab() {
  local requested="${FLUTTER_ATLAS_DEVICE_ID:-${FLUTTER_DEVICE_ID:-}}"
  if [[ -z "$requested" ]]; then
    echo "Cleanup対象IDが未指定です。AVD、Simulator、Application Dataは変更しません。"
    return 0
  fi
  if command -v adb >/dev/null 2>&1 && adb -s "$requested" get-state >/dev/null 2>&1; then
    if [[ "$(android_property "$requested" ro.kernel.qemu)" != "1" ]]; then
      die "$requested はAndroid実機のため、Simulator ProfileからCleanupしません。"
    fi
    adb -s "$requested" shell am force-stop "$application_id" >/dev/null
    echo "Android Emulator上の対象Applicationだけを停止しました。AVD、Application Data、Evidenceは保持します。"
    return 0
  fi
  if command -v xcrun >/dev/null 2>&1 && xcrun simctl list devices booted | grep -Fq "$requested"; then
    xcrun simctl terminate "$requested" "$application_id" >/dev/null 2>&1 || true
    echo "iOS Simulator上の対象Applicationだけを停止しました。Simulator、Application Data、Evidenceは保持します。"
    return 0
  fi
  echo "対象Runnerは停止済みまたは到達不能です。AVD、Simulator、Application Data、Evidenceは変更しません。"
}

configure_toolchains

case "$action" in
  doctor)
    device_id="$(resolve_device_id)"
    runner_kind="$(detect_runner_kind "$device_id")"
    write_inventory "$device_id" "$runner_kind"
    ;;
  run)
    device_id="$(resolve_device_id)"
    runner_kind="$(detect_runner_kind "$device_id")"
    run_lab "$device_id" "$runner_kind"
    ;;
  cleanup)
    cleanup_lab
    ;;
  *)
    echo "使い方: scripts/labs-simulator.sh doctor|run|cleanup" >&2
    exit 2
    ;;
esac
