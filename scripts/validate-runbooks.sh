#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
required=(
  "$repo_root/operations/README.md"
  "$repo_root/operations/UPGRADE.md"
  "$repo_root/operations/INCIDENT.md"
)
for path in "${required[@]}"; do
  test -s "$path" || { echo "エラー: Runbookがありません: $path" >&2; exit 1; }
done
echo "Runbook構造を検証しました。"
