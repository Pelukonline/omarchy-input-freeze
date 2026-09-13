#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
helper="${repo_dir}/input-freeze"

bash -n "$helper"

python3 -m unittest discover -s "$repo_dir/tests" -p 'test_*.py' -v

jq -e '
  .schemaVersion == 1 and
  .id == "io.github.pelukonline.input-freeze" and
  .kinds == ["bar-widget"] and
  .entryPoints.barWidget == "BarWidget.qml"
' "${repo_dir}/manifest.json" >/dev/null
