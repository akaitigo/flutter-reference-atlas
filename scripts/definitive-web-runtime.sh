#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
workspace="$repo_root/reference-systems/operations-workspace"
output_dir="$repo_root/.tools/definitive-web"
artifact="${FLUTTER_ATLAS_WEB_ARTIFACT:-$repo_root/evidence/artifacts/definitive-web-chrome-report.json}"
js_evidence_log="${FLUTTER_ATLAS_WEB_JS_LOG:-$repo_root/evidence/artifacts/definitive-web-chrome-js.log}"
wasm_evidence_log="${FLUTTER_ATLAS_WEB_WASM_LOG:-$repo_root/evidence/artifacts/definitive-web-chrome-wasm.log}"
test_file="$workspace/test/workspace_app_test.dart"

die() {
  echo "エラー: $*" >&2
  exit 1
}

[[ -x "$flutter_bin" ]] || die "固定Flutter SDKがありません: $sdk_root"
mkdir -p "$output_dir" "$repo_root/.tools/xdg-config"
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
set +e
(
  cd "$workspace"
  "$flutter_bin" test --platform chrome test/workspace_app_test.dart --no-pub
) 2>&1 | tee "$output_dir/chrome-js.log"
js_exit=${PIPESTATUS[0]}
(
  cd "$workspace"
  "$flutter_bin" test --platform chrome --wasm test/workspace_app_test.dart --no-pub
) 2>&1 | tee "$output_dir/chrome-wasm.log"
wasm_exit=${PIPESTATUS[0]}
set -e
finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

python3 "$repo_root/tooling/definitive_web/report.py" \
  --output "$artifact" \
  --js-log "$output_dir/chrome-js.log" \
  --wasm-log "$output_dir/chrome-wasm.log" \
  --js-evidence-log "$js_evidence_log" \
  --wasm-evidence-log "$wasm_evidence_log" \
  --test-file "$test_file" \
  --pubspec-lock "$workspace/pubspec.lock" \
  --started-at "$started_at" \
  --finished-at "$finished_at" \
  --js-exit-code "$js_exit" \
  --wasm-exit-code "$wasm_exit"

[[ "$js_exit" == "0" ]] || die "Chrome JavaScript Runtime Testが失敗しました。"
[[ "$wasm_exit" == "0" ]] || die "Chrome Wasm Runtime Testが失敗しました。"
echo "Chrome JS/Wasm Runtime Evidenceを生成しました: $artifact"
