#!/usr/bin/env bash
set -euo pipefail

required_files=("PROJECT_SPEC.md" "ARCHITECTURE.md" "TASKS.md" "AGENTS.md")

missing=0
for f in "${required_files[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing required file: $f"
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  exit 1
fi

echo "Repo structure validated."
