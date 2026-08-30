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
run_id="${FLUTTER_ATLAS_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
work_root="$repo_root/.tools/scenario-security-tranche/runs/$run_id"
reporter="$repo_root/tooling/scenario_security_tranche/report.py"
failure_recorder="$repo_root/tooling/scenario_security_tranche/failure_record.py"
device_id="${FLUTTER_ATLAS_DEVICE_ID:-}"
package_name="dev.akaitigo.atlas.operations_workspace"
started_emulator=false
finalize="${FLUTTER_ATLAS_FINALIZE:-true}"
marker_timeout_seconds="${FLUTTER_ATLAS_MARKER_TIMEOUT_SECONDS:-300}"
completion_timeout_seconds="${FLUTTER_ATLAS_COMPLETION_TIMEOUT_SECONDS:-300}"

surfaces=(
  accessibility.focus-text-scale
  accessibility.semantics-tree
  background.app-lifecycle
  background.isolate-work
  input.focus-traversal
  input.keyboard-shortcuts
  input.pointer-gesture-arena
  input.text-ime
)

if [[ -n "${FLUTTER_ATLAS_SURFACES:-}" ]]; then
  read -r -a selected_surfaces <<<"$FLUTTER_ATLAS_SURFACES"
else
  selected_surfaces=("${surfaces[@]}")
fi

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
    input.focus-traversal) echo "ordered-traversal skip-sensitive" ;;
    input.keyboard-shortcuts) echo "shortcuts-actions callback-shortcuts" ;;
    input.pointer-gesture-arena) echo "tap-recognizer horizontal-drag" ;;
    input.text-ime) echo "obscured-entry bidi-rejection" ;;
    *) die "未対応Surfaceです: $1" ;;
  esac
}

is_known_surface() {
  local candidate="$1"
  local known=""
  for known in "${surfaces[@]}"; do
    [[ "$candidate" == "$known" ]] && return 0
  done
  return 1
}

write_or_compare() {
  local path="$1"
  local value="$2"
  if [[ -f "$path" ]]; then
    [[ "$(<"$path")" == "$value" ]] || die "同一run IDのRuntime identityが変化しました: $(basename "$path")"
  else
    printf '%s\n' "$value" >"$path"
  fi
}

wait_for_test_exit() {
  local pid="$1"
  local seconds="$2"
  local ticks=$((seconds * 10))
  for _ in $(seq 1 "$ticks"); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

terminate_test() {
  local pid="$1"
  terminated_exit=124
  kill -TERM "$pid" >/dev/null 2>&1 || true
  for _ in $(seq 1 100); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      break
    fi
    sleep 0.1
  done
  if kill -0 "$pid" >/dev/null 2>&1; then
    kill -KILL "$pid" >/dev/null 2>&1 || true
  fi
  set +e
  wait "$pid" >/dev/null 2>&1
  terminated_exit=$?
  set -e
}

record_failure() {
  local phase="$1"
  local exit_code="$2"
  python3 "$failure_recorder" \
    --output "$row_dir/failure.json" \
    --repo-root "$repo_root" \
    --log "$log_path" \
    --run-id "$run_id" \
    --phase "$phase" \
    --surface "$surface" \
    --variant "$variant" \
    --exit-code "$exit_code" \
    --device-id "$device_id" \
    --os-version "$os_version" \
    --api-level "$api_level" \
    --architecture "$architecture" \
    --source-digest "$(<"$work_root/source-sha256.txt")" \
    --harness-digest "$(<"$work_root/harness-sha256.txt")"
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
[[ -x "$failure_recorder" ]] || die "security-001 Failure Recorderがありません: $failure_recorder"
[[ "$finalize" == "true" || "$finalize" == "false" ]] || die "FLUTTER_ATLAS_FINALIZEはtrue/falseで指定してください。"
[[ "$marker_timeout_seconds" =~ ^[1-9][0-9]*$ ]] || die "marker timeoutは正整数で指定してください。"
[[ "$completion_timeout_seconds" =~ ^[1-9][0-9]*$ ]] || die "completion timeoutは正整数で指定してください。"
for surface in "${selected_surfaces[@]}"; do
  is_known_surface "$surface" || die "未対応Surfaceです: $surface"
done

mkdir -p "$work_root" "$(dirname "$runtime_test")" "$repo_root/.tools/xdg-config"
write_or_compare "$work_root/source-sha256.txt" "$(shasum -a 256 "$source_test" | awk '{print $1}')"
write_or_compare "$work_root/harness-sha256.txt" "$(shasum -a 256 "${BASH_SOURCE[0]}" | awk '{print $1}')"
cp "$source_test" "$runtime_test"
export ANDROID_HOME="$android_sdk"
export ANDROID_SDK_ROOT="$android_sdk"
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

(cd "$workspace" && "$flutter_bin" pub get --suppress-analytics) >"$work_root/pub-get.log" 2>&1

resolve_emulator
[[ "$(android_property ro.kernel.qemu)" == "1" ]] || die "$device_id はAndroid Emulatorではありません。"
api_level="$(android_property ro.build.version.sdk)"
[[ "$api_level" == "36" ]] || die "Android API 36が必要です: observed=$api_level"
os_version="$(android_property ro.build.version.release)"
architecture="$(android_property ro.product.cpu.abi)"
write_or_compare "$work_root/device-id.txt" "$device_id"
write_or_compare "$work_root/os-version.txt" "$os_version"
write_or_compare "$work_root/api-level.txt" "$api_level"
write_or_compare "$work_root/architecture.txt" "$architecture"
if [[ ! -f "$work_root/started-at.txt" ]]; then
  date -u +%Y-%m-%dT%H:%M:%SZ >"$work_root/started-at.txt"
fi
started_at="$(<"$work_root/started-at.txt")"

for surface in "${selected_surfaces[@]}"; do
  for variant in $(variants_for "$surface"); do
    row_dir="$work_root/$surface/$variant"
    log_path="$row_dir/runtime.log"
    screen_path="$row_dir/screen.png"
    if [[ "$surface" == accessibility.* ]]; then
      platform_path="$row_dir/platform-tree.xml"
    else
      platform_path="$row_dir/platform-state.txt"
    fi
    [[ ! -e "$row_dir" ]] || die "$surface:$variant は同一run IDで既に開始済みです。上書き・再試行しません。"
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
    for _ in $(seq 1 "$((marker_timeout_seconds * 10))"); do
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
    if [[ "$marker_seen" == false ]] && kill -0 "$test_pid" >/dev/null 2>&1; then
      terminate_test "$test_pid"
      record_failure "marker-timeout" "$terminated_exit"
      die "$surface:$variant のRuntime marker待機が${marker_timeout_seconds}秒を超過しました。部分runを保持し、再試行しません: $log_path"
    fi
    if [[ "$marker_seen" == true ]]; then
      remote_tree="/sdcard/atlas-security-${surface//./-}-$variant.xml"
      "$adb_bin" -s "$device_id" shell am start -W -n "$package_name/.MainActivity" >/dev/null
      sleep 1
      "$adb_bin" -s "$device_id" exec-out screencap -p >"$screen_path"
      if [[ "$surface" == accessibility.* ]]; then
        "$adb_bin" -s "$device_id" shell uiautomator dump "$remote_tree" >/dev/null
        "$adb_bin" -s "$device_id" exec-out cat "$remote_tree" >"$platform_path"
        grep -Fq '<hierarchy' "$platform_path" || die "$surface:$variant のPlatform treeを取得できません。成功Evidenceは保持します。"
      else
        {
          printf 'ATLAS_PLATFORM_STATE surface=%s variant=%s\n' "$surface" "$variant"
          "$adb_bin" -s "$device_id" shell dumpsys activity top
        } >"$platform_path"
        grep -Fq "$package_name" "$platform_path" || die "$surface:$variant のAndroid Activity stateを取得できません。成功Evidenceは保持します。"
      fi
    fi
    if ! wait_for_test_exit "$test_pid" "$completion_timeout_seconds"; then
      terminate_test "$test_pid"
      record_failure "post-marker-timeout" "$terminated_exit"
      die "$surface:$variant のmarker後完了待機が${completion_timeout_seconds}秒を超過しました。部分runを保持し、再試行しません: $log_path"
    fi
    set +e
    wait "$test_pid"
    exit_code=$?
    set -e
    if [[ "$exit_code" != "0" ]]; then
      record_failure "test-exit" "$exit_code"
      die "$surface:$variant のfirst-attempt実行が失敗しました。成功Evidenceは保持します: $log_path"
    fi
    [[ "$marker_seen" == true ]] || die "$surface:$variant のRuntime markerを取得できません。成功Evidenceは保持します。"
  done
done

if [[ "$finalize" == "false" ]]; then
  echo "security-001/005 staging chunk完了: run=$run_id surfaces=${#selected_surfaces[@]} attempts=1 retries=0"
  exit 0
fi

report_args=()
for surface in "${surfaces[@]}"; do
  for variant in $(variants_for "$surface"); do
    row_dir="$work_root/$surface/$variant"
    log_path="$row_dir/runtime.log"
    screen_path="$row_dir/screen.png"
    if [[ "$surface" == accessibility.* ]]; then
      platform_path="$row_dir/platform-tree.xml"
    else
      platform_path="$row_dir/platform-state.txt"
    fi
    [[ -s "$log_path" && -s "$screen_path" && -s "$platform_path" ]] || die "$surface:$variant のstaging Artifactが揃っていません。"
    grep -Fq "All tests passed!" "$log_path" || die "$surface:$variant のfirst-attempt成功を確認できません。"
    report_args+=(
      --log "$surface:$variant=$log_path"
      --screenshot "$surface:$variant=$screen_path"
      --tree "$surface:$variant=$platform_path"
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

echo "security-001/005専用Runtime完了: rows=8 variants=2 attempts=1 retries=0"
