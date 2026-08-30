#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
android_sdk="${ANDROID_SDK_ROOT:-${ANDROID_HOME:-${HOME}/Library/Android/sdk}}"
flutter_bin="$sdk_root/bin/flutter"
adb_bin="$android_sdk/platform-tools/adb"
apkanalyzer="$android_sdk/cmdline-tools/latest/bin/apkanalyzer"
apksigner="$android_sdk/build-tools/35.0.0/apksigner"
emulator_bin="$android_sdk/emulator/emulator"
workspace="$repo_root/reference-systems/operations-workspace"
source_entry="$repo_root/tooling/scenario_build_android/build_security_main.dart"
reporter="$repo_root/tooling/scenario_build_android/report.py"
output="$repo_root/evidence/scenarios/runtime"
work_root="$repo_root/.tools/scenario-build-android-security/runs/$(date -u +%Y%m%dT%H%M%SZ)"
package_name="dev.akaitigo.atlas.operations_workspace"
avd_name="${FLUTTER_ATLAS_ANDROID_AVD:-medium_phone}"
device_id="${FLUTTER_ATLAS_DEVICE_ID:-}"
started_emulator=false

die() { echo "エラー: $*" >&2; exit 1; }

android_property() {
  "$adb_bin" -s "$device_id" shell getprop "$1" 2>/dev/null | tr -d '\r'
}

resolve_emulator() {
  local candidate=""
  if [[ -n "$device_id" ]] && "$adb_bin" -s "$device_id" get-state >/dev/null 2>&1; then
    if [[ "$(android_property sys.boot_completed)" == "1" ]]; then
      sleep 2
      "$adb_bin" -s "$device_id" get-state >/dev/null 2>&1 && return 0
    fi
  fi
  candidate="$("$adb_bin" devices | awk 'NR > 1 && $2 == "device" && $1 ~ /^emulator-/ { print $1; exit }')"
  if [[ -n "$candidate" ]]; then
    device_id="$candidate"
    if [[ "$(android_property sys.boot_completed)" == "1" ]]; then
      sleep 2
      "$adb_bin" -s "$device_id" get-state >/dev/null 2>&1 && return 0
    fi
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
      [[ "$(android_property sys.boot_completed)" == "1" ]] && return 0
    fi
    sleep 1
  done
  die "Android Emulatorのbootが120秒以内に完了しませんでした。"
}

cleanup() {
  if [[ -n "$device_id" ]]; then
    "$adb_bin" -s "$device_id" shell am force-stop "$package_name" >/dev/null 2>&1 || true
    if [[ "$started_emulator" == true ]]; then "$adb_bin" -s "$device_id" emu kill >/dev/null 2>&1 || true; fi
  fi
}
trap cleanup EXIT

for required in "$flutter_bin" "$adb_bin" "$apkanalyzer" "$apksigner" "$emulator_bin" "$reporter"; do
  [[ -x "$required" ]] || die "実行Fileがありません: $required"
done
[[ -f "$source_entry" ]] || die "専用entrypointがありません: $source_entry"
mkdir -p "$work_root" "$repo_root/.tools/xdg-config"
export ANDROID_HOME="$android_sdk" ANDROID_SDK_ROOT="$android_sdk" FLUTTER_SUPPRESS_ANALYTICS=true XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"
resolve_emulator
[[ "$(android_property ro.kernel.qemu)" == "1" ]] || die "$device_id はAndroid Emulatorではありません。"
api_level="$(android_property ro.build.version.sdk)"
[[ "$api_level" == "36" ]] || die "Android API 36が必要です: observed=$api_level"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
report_args=()

for variant in debug-apk-install release-apk; do
  row="$work_root/$variant"
  mkdir -p "$row"
  mode="debug"
  [[ "$variant" == "release-apk" ]] && mode="release"
  (
    cd "$workspace"
    "$flutter_bin" build apk "--$mode" --split-per-abi --target "$source_entry" --dart-define="ATLAS_VARIANT=$variant"
  ) >"$row/build.log" 2>&1
  apk="$workspace/build/app/outputs/flutter-apk/app-arm64-v8a-$mode.apk"
  [[ -s "$apk" ]] || die "$variant APKがありません。"
  cp "$apk" "$row/app.apk"
  "$apkanalyzer" manifest print "$row/app.apk" >"$row/manifest.xml"
  "$apksigner" verify --print-certs "$row/app.apk" >"$row/signing.txt"
  "$adb_bin" -s "$device_id" shell am force-stop "$package_name" >/dev/null
  "$adb_bin" -s "$device_id" install -r "$row/app.apk" >"$row/install.log"
  "$adb_bin" -s "$device_id" shell am start -W -n "$package_name/.MainActivity" >"$row/launch.log"
  sleep 3
  "$adb_bin" -s "$device_id" exec-out screencap -p >"$row/screen.png"
  remote_tree="/sdcard/atlas-build-security-$variant.xml"
  "$adb_bin" -s "$device_id" shell uiautomator dump "$remote_tree" >/dev/null
  "$adb_bin" -s "$device_id" exec-out cat "$remote_tree" >"$row/platform-tree.xml"
  grep -Fq '<hierarchy' "$row/platform-tree.xml" || die "$variant のPlatform treeを取得できません。"
  grep -Fq "build android security $variant PASS" "$row/platform-tree.xml" || die "$variant の専用PASS画面を取得できません。"
  report_args+=(
    --input "$variant=apk=$row/app.apk"
    --input "$variant=manifest=$row/manifest.xml"
    --input "$variant=signing=$row/signing.txt"
    --input "$variant=screen=$row/screen.png"
    --input "$variant=tree=$row/platform-tree.xml"
  )
done

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
runtime_identity="$(printf '{"profile":"android-emulator","runner_kind":"android-emulator","os":"Android %s","architecture":"%s","api_level":%s,"device_id":"%s","physical_device":false}' "$(android_property ro.build.version.release)" "$(android_property ro.product.cpu.abi)" "$api_level" "$device_id")"
python3 "$reporter" \
  --repo-root "$repo_root" --output "$output" --sdk-root "$sdk_root" \
  --harness "$repo_root/scripts/scenario-build-android-security-runtime.sh" --source "$source_entry" \
  --started-at "$started_at" --completed-at "$completed_at" --runtime-identity "$runtime_identity" \
  "${report_args[@]}"

echo "build.android security Runtime完了: variants=2 attempts=1 retries=0"
