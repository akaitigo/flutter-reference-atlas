#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
workspace="$repo_root/reference-systems/operations-workspace"
output_dir="$repo_root/.tools/reference-scenario-runtime"
chrome_bin="${FLUTTER_ATLAS_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
trace_output_root="${FLUTTER_ATLAS_SCENARIO_OUTPUT_ROOT:-evidence/scenarios/integrated}"

[[ -x "$flutter_bin" ]] || { echo "エラー: 固定Flutter SDKがありません: $sdk_root" >&2; exit 1; }
[[ -x "$chrome_bin" ]] || { echo "エラー: Google Chromeがありません: $chrome_bin" >&2; exit 1; }
mkdir -p "$output_dir" "$repo_root/.tools/xdg-config"
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

set +e
(
  cd "$workspace"
  "$flutter_bin" test --platform chrome test/scenario_trace_test.dart --no-pub --machine
) >"$output_dir/javascript.machine.jsonl" 2>"$output_dir/javascript.stderr.log"
js_exit=$?
(
  cd "$workspace"
  "$flutter_bin" test --platform chrome --wasm test/scenario_trace_test.dart --no-pub --machine
) >"$output_dir/wasm.machine.jsonl" 2>"$output_dir/wasm.stderr.log"
wasm_exit=$?
set -e

[[ "$js_exit" == "0" ]] || { echo "エラー: Chrome JavaScript Scenario Testが失敗しました。" >&2; exit 1; }
[[ "$wasm_exit" == "0" ]] || { echo "エラー: Chrome Wasm Scenario Testが失敗しました。" >&2; exit 1; }

browser_version="$("$chrome_bin" --version | sed -E 's/^Google Chrome[[:space:]]+//; s/[[:space:]]+$//')"
python3 "$repo_root/tooling/scenario_proof/capture_runtime.py" \
  --js-log "$output_dir/javascript.machine.jsonl" \
  --wasm-log "$output_dir/wasm.machine.jsonl" \
  --browser-version "$browser_version" \
  --platform "$(uname -s)" \
  --architecture "$(uname -m)" \
  --flutter-version "3.47.1" \
  --dart-version "3.13.1" \
  --output-root "$trace_output_root"
