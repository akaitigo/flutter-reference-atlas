#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
sdk_root="${FLUTTER_ATLAS_SDK_ROOT:-$repo_root/.tools/flutter-3.47.1/flutter}"
flutter_bin="$sdk_root/bin/flutter"
workspace="$repo_root/reference-systems/operations-workspace"
source_entry="$repo_root/tooling/scenario_build_web/build_security_main.dart"
reporter="$repo_root/tooling/scenario_build_web/report.py"
capture="$repo_root/tooling/scenario_build_web/capture.py"
output="$repo_root/evidence/scenarios/runtime"
chrome_bin="${FLUTTER_ATLAS_CHROME_BIN:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
work_root="$repo_root/.tools/scenario-build-web-security/runs/$(date -u +%Y%m%dT%H%M%SZ)"
server_pids=()
chrome_pids=()

die() { echo "エラー: $*" >&2; exit 1; }

cleanup() {
  for server_pid in "${server_pids[@]:-}"; do
    kill "$server_pid" >/dev/null 2>&1 || true
    wait "$server_pid" >/dev/null 2>&1 || true
  done
  for chrome_pid in "${chrome_pids[@]:-}"; do
    kill "$chrome_pid" >/dev/null 2>&1 || true
    wait "$chrome_pid" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

for required in "$flutter_bin" "$chrome_bin" "$reporter" "$capture"; do
  [[ -x "$required" ]] || die "実行Fileがありません: $required"
done
[[ -f "$source_entry" ]] || die "専用entrypointがありません: $source_entry"
mkdir -p "$work_root" "$repo_root/.tools/xdg-config"
export FLUTTER_SUPPRESS_ANALYTICS=true XDG_CONFIG_HOME="$repo_root/.tools/xdg-config"

(cd "$workspace" && "$flutter_bin" pub get --suppress-analytics) >"$work_root/pub-get.log" 2>&1
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
report_args=()
for variant in javascript release-js wasm; do
  row="$work_root/$variant"
  build_dir="$row/build"
  mkdir -p "$row"
  build_flags=(--no-pub --target "$source_entry" --output "$build_dir" --dart-define="ATLAS_VARIANT=$variant" --suppress-analytics)
  case "$variant" in
    javascript)
      build_flags=(--debug --source-maps --no-wasm-dry-run "${build_flags[@]}")
      mode="debug-javascript-with-source-maps"
      artifact="$build_dir/main.dart.js"
      ;;
    release-js)
      build_flags=(--release --csp --no-source-maps --no-wasm-dry-run "${build_flags[@]}")
      mode="release-javascript-csp-no-source-maps"
      artifact="$build_dir/main.dart.js"
      ;;
    wasm)
      build_flags=(--release --wasm --no-source-maps "${build_flags[@]}")
      mode="release-wasm-no-source-maps"
      artifact="$build_dir/main.dart.wasm"
      ;;
  esac
  (cd "$workspace" && "$flutter_bin" build web "${build_flags[@]}") >"$row/build.log" 2>&1
  [[ -s "$artifact" && -s "$build_dir/index.html" ]] || die "$variant のWeb build artifactがありません。"
  if [[ "$variant" == "javascript" ]]; then
    [[ -s "$build_dir/main.dart.js.map" ]] || die "javascript debug source mapがありません。"
  else
    [[ ! -e "$build_dir/main.dart.js.map" && ! -e "$build_dir/main.dart.wasm.map" ]] || die "$variant にsource mapが残っています。"
  fi
  printf '%s\n' "$mode" >"$row/mode.txt"
  port="$(python3 -c 'import socket; listener = socket.socket(); listener.bind(("127.0.0.1", 0)); print(listener.getsockname()[1]); listener.close()')"
  python3 -m http.server "$port" --bind 127.0.0.1 --directory "$build_dir" >"$row/server.log" 2>&1 &
  server_pid=$!
  server_pids+=("$server_pid")
  sleep 1
  kill -0 "$server_pid" >/dev/null 2>&1 || die "$variant のlocalhost serverを開始できません。"
  curl --fail --silent --show-error "http://127.0.0.1:$port/" >/dev/null || die "$variant のlocalhost buildへ接続できません。"
  "$chrome_bin" --headless=new --disable-gpu --disable-dev-shm-usage --disable-background-networking \
    --disable-component-update --disable-sync --metrics-recording-only --force-renderer-accessibility \
    --no-first-run --no-default-browser-check \
    --remote-debugging-port=0 --remote-allow-origins=* --user-data-dir="$row/chrome-profile" \
    --window-size=1280,800 --hide-scrollbars "http://127.0.0.1:$port/" \
    >"$row/chrome.stdout.log" 2>"$row/chrome.log" &
  chrome_pid=$!
  chrome_pids+=("$chrome_pid")
  python3 "$capture" --user-data-dir "$row/chrome-profile" \
    --observation "$row/observation.json" --tree "$row/platform-tree.json" --screenshot "$row/screen.png"
  kill "$chrome_pid" >/dev/null 2>&1 || true
  wait "$chrome_pid" >/dev/null 2>&1 || true
  kill "$server_pid" >/dev/null 2>&1 || true
  wait "$server_pid" >/dev/null 2>&1 || true
  grep -Fq '"flutterView": true' "$row/observation.json" || die "$variant の実Chrome first-frameを取得できません。"
  grep -Fq '"accessibility"' "$row/platform-tree.json" || die "$variant のAccessibility treeを取得できません。"
  [[ -s "$row/screen.png" ]] || die "$variant の実Chrome screenshotがありません。"
  report_args+=(
    --input "$variant=artifact=$artifact"
    --input "$variant=index=$build_dir/index.html"
    --input "$variant=observation=$row/observation.json"
    --input "$variant=tree=$row/platform-tree.json"
    --input "$variant=screen=$row/screen.png"
    --input "$variant=buildlog=$row/build.log"
    --input "$variant=chromelog=$row/chrome.log"
    --input "$variant=mode=$row/mode.txt"
  )
done

completed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
chrome_version="$("$chrome_bin" --version | sed 's/^Google Chrome //' | awk '{$1=$1; print}')"
runtime_identity="$(printf '{"profile":"web-chrome","runner_kind":"browser-runtime","os":"macOS %s","architecture":"%s","browser":"Google Chrome","browser_version":"%s","physical_device":false}' "$(sw_vers -productVersion)" "$(uname -m)" "$chrome_version")"
python3 "$reporter" \
  --repo-root "$repo_root" --output "$output" --sdk-root "$sdk_root" \
  --harness "$repo_root/scripts/scenario-build-web-security-runtime.sh" --source "$source_entry" \
  --started-at "$started_at" --completed-at "$completed_at" --runtime-identity "$runtime_identity" \
  "${report_args[@]}"

echo "build.web security Runtime完了: variants=3 attempts=1 retries=0"
