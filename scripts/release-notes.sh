#!/usr/bin/env bash
# Print the CHANGELOG.md section for a version. Usage: release-notes.sh 0.3.0
set -euo pipefail
version="${1:?version like 0.3.0}"
file="$(dirname "$0")/../CHANGELOG.md"
notes="$(awk -v v="$version" '
  /^## / { if (on) exit; on = ($2 == v) ; next }
  on { print }
' "$file" | sed -e '/./,$!d')"
if [ -z "$notes" ]; then
  echo "CHANGELOG.md has no section for $version" >&2
  exit 1
fi
printf '%s\n' "$notes"
