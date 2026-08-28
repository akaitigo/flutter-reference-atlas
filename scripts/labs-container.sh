#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image_name="flutter-atlas-dart-lab:local"
cleanup() {
  docker image rm "$image_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker build --network none -f "$repo_root/environments/container/Dockerfile" -t "$image_name" "$repo_root"
docker run --rm --network none "$image_name"
