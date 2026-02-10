#!/usr/bin/env bash
set -euo pipefail

# Minimal initializer placeholder. Extend as needed.

if [[ -z "${1:-}" ]]; then
  echo "Usage: scripts/init_project.sh <project-name>"
  exit 1
fi

PROJECT_NAME="$1"

echo "Initializing project: ${PROJECT_NAME}"

# Example: create baseline folders
mkdir -p src tests

echo "Done. Update PROJECT_SPEC.md, ARCHITECTURE.md, and TASKS.md."
