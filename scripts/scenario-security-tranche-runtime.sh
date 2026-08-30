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
workspace="$repo_root/reference-systems/operations-workspace"
source_test="$repo_root/tooling/scenario_security_tranche/security_tranche_scenario_test.dart"
runtime_test="$workspace/integration_test/.atlas-generated/security_tranche_scenario_test.dart"
output_root="$repo_root/evidence/scenarios/runtime"
work_root="$repo_root/.tools/scenario-security-tranche/runs/$(date -u +%Y%m%dT%H%M%SZ)"
reporter="$repo_root/tooling/scenario_security_tranche/report.py"
device_id="${FLUTTER_ATLAS_DEVICE_ID:-}"
package_name="dev.akaitigo.atlas.operations_workspace"
started_emulator=false

surfaces=(
  accessibility.focus-text-scale
  accessibility.semantics-tree
  background.app-lifecycle
  background.isolate-work
)

die() {
  echo "エラー: $*" >&2
  exit 1
}

variants_for() {
  case "$1" in
    accessibility.focus-text-scale) echo "text-scale-1x text-scale-2x" ;;
    accessibility.semantics-tree) echo "material-semantics explicit-container" ;;
    background.app-lifecycle) echo "app-lifecycle-listener widgets-binding-observer" ;;
    background.isolate-work) echo "isolate-run transferable-data" ;;
    *) die "未対応Surfaceです: $1" ;;
  esac
}

android_property() {
  "$adb_bin" -s "$device_id" shell getprop "$1" 2>/dev/null | tr -d '\r'
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
  mkdir -p "$work_root"
  "$emulator_bin" "@$avd_name" -no-snapshot-save -no-boot-anim >"$work_root/emulator.log" 2>&1 &
  started_emulator=true
  "$adb_bin" wait-for-device
  for _ in $(seq 1 120); do
    candidate="$("$adb_bin" devices | awk 'NR > 1 && $2 == "device" && $1 ~ /^emulator-/ { print $1; exit }')"
    if [[ -n "$candidate" ]]; then
      device_id="$candidate"
      if [[ "$(android_property sys.boot_completed)" == "1" ]]; then
        return 0
      fi
    fi
    sleep 1
  done
  die "Android Emulatorのbootが120秒以内に完了しませんでした。"
}

cleanup() {
  if [[ -n "$device_id" ]]; then
    "$adb_bin" -s "$device_id" shell am force-stop "$package_name" >/dev/null 2>&1 || true
    if [[ "$started_emulator" == true ]]; then
      "$adb_bin" -s "$device_id" emu kill >/dev/null 2>&1 || true
    fi
  fi
}
trap cleanup EXIT

[[ -x "$flutter_bin" ]] || die "固定Flutter SDKがありません: $sdk_root"
[[ -x "$adb_bin" ]] || die "adbがありません: $adb_bin"
[[ -x "$emulator_bin" ]] || die "Android Emulatorがありません: $emulator_bin"
[[ -f "$source_test" ]] || die "security-001 Scenario Testがありません: $source_test"
[[ -x "$reporter" ]] || die "security-001 Reporterがありません: $reporter"

mkdir -p "$work_root" "$(dirname "$runtime_test")" "$repo_root/.tools/xdg-config"
cp "$source_test" "$runtime_test"
export ANDROID_HOME="$android_sdk"
export ANDROID_SDK_ROOT="$android_sdk"
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

resolve_emulator
[[ "$(android_property ro.kernel.qemu)" == "1" ]] || die "$device_id はAndroid Emulatorではありません。"
api_level="$(android_property ro.build.version.sdk)"
[[ "$api_level" == "36" ]] || die "Android API 36が必要です: observed=$api_level"
os_version="$(android_property ro.build.version.release)"
architecture="$(android_property ro.product.cpu.abi)"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

report_args=()
for surface in "${surfaces[@]}"; do
  for variant in $(variants_for "$surface"); do
    row_dir="$work_root/$surface/$variant"
    log_path="$row_dir/runtime.log"
    screen_path="$row_dir/screen.png"
    tree_path="$row_dir/platform-tree.xml"
    mkdir -p "$row_dir"
    "$adb_bin" -s "$device_id" shell am force-stop "$package_name" >/dev/null
    (
      cd "$workspace"
      "$flutter_bin" test \
        --dart-define="ATLAS_SURFACE=$surface" \
        --dart-define="ATLAS_VARIANT=$variant" \
        integration_test/.atlas-generated/security_tranche_scenario_test.dart \
        -d "$device_id" --no-pub
    ) >"$log_path" 2>&1 &
    test_pid=$!
    marker_seen=false
    action_sent=false
    for _ in $(seq 1 9000); do
      if [[ "$action_sent" == false ]] && grep -Fq "ATLAS_HOST_ACTION:background-and-resume" "$log_path" 2>/dev/null; then
        "$adb_bin" -s "$device_id" shell input keyevent KEYCODE_HOME
        sleep 1
        "$adb_bin" -s "$device_id" shell am start -W -n "$package_name/.MainActivity" >/dev/null
        action_sent=true
      fi
      if grep -Fq "ATLAS_CAPTURE_READY:$surface:$variant" "$log_path" 2>/dev/null; then
        marker_seen=true
        break
      fi
      if ! kill -0 "$test_pid" >/dev/null 2>&1; then
        break
      fi
      sleep 0.1
    done
    if [[ "$marker_seen" == true ]]; then
      remote_tree="/sdcard/atlas-security-${surface//./-}-$variant.xml"
      "$adb_bin" -s "$device_id" shell am start -W -n "$package_name/.MainActivity" >/dev/null
      sleep 1
      "$adb_bin" -s "$device_id" exec-out screencap -p >"$screen_path"
      "$adb_bin" -s "$device_id" shell uiautomator dump "$remote_tree" >/dev/null
      "$adb_bin" -s "$device_id" exec-out cat "$remote_tree" >"$tree_path"
      grep -Fq '<hierarchy' "$tree_path" || die "$surface:$variant のPlatform treeを取得できません。成功Evidenceは保持します。"
    fi
    set +e
    wait "$test_pid"
    exit_code=$?
    set -e
    [[ "$exit_code" == "0" ]] || die "$surface:$variant のfirst-attempt実行が失敗しました。成功Evidenceは保持します: $log_path"
    [[ "$marker_seen" == true ]] || die "$surface:$variant のRuntime markerを取得できません。成功Evidenceは保持します。"
    report_args+=(
      --log "$surface:$variant=$log_path"
      --screenshot "$surface:$variant=$screen_path"
      --tree "$surface:$variant=$tree_path"
    )
  done
done

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
python3 "$reporter" \
  --repo-root "$repo_root" \
  --output "$output_root" \
  --harness "$repo_root/scripts/scenario-security-tranche-runtime.sh" \
  --source "$source_test" \
  --device-id "$device_id" \
  --os-version "$os_version" \
  --api-level "$api_level" \
  --architecture "$architecture" \
  --started-at "$started_at" \
  --completed-at "$completed_at" \
  "${report_args[@]}"

echo "security-001専用Runtime完了: rows=4 variants=2 attempts=1 retries=0"
