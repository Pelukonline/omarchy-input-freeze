#!/usr/bin/env bash

set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
helper="${repo_dir}/input-freeze"

bash -n "$helper"

# Regression: a first run has no disabled-pointers state file. Cleanup must
# still succeed under `set -e` instead of aborting activation or recovery.
if ! awk '
  /clear_device_state\(\)/ { in_function = 1 }
  in_function && /return 0/ { found = 1 }
  in_function && /^}/ { exit(found ? 0 : 1) }
  END { if (!in_function) exit 1 }
' "$helper"; then
  echo "clear_device_state must explicitly succeed when state is absent" >&2
  exit 1
fi

jq -e '
  .schemaVersion == 1 and
  .id == "io.github.pelukonline.input-freeze" and
  .kinds == ["bar-widget"] and
  .entryPoints.barWidget == "BarWidget.qml"
' "${repo_dir}/manifest.json" >/dev/null
