#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

common=(--hidden -g '!.git/**' -g '!.tools/**' -g '!scripts/check-publication-hygiene.sh')
if rg -n "${common[@]}" '/Users/[^$]|nakayamaryuuukei|private-code' .; then
  echo 'エラー: 公開Artifactにローカル個人Pathが含まれています。' >&2
  exit 1
fi
if rg -n "${common[@]}" 'AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9_]{20,}|-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----|password[[:space:]]*[:=][[:space:]]*[^< ]' .; then
  echo 'エラー: Credentialまたは秘密らしき文字列が含まれています。' >&2
  exit 1
fi

echo 'Publication hygieneを検証しました。'
