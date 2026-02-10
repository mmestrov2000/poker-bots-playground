#!/usr/bin/env bash
set -euo pipefail

required_files=(
  "PROJECT_SPEC.md"
  "ARCHITECTURE.md"
  "TASKS.md"
  "AGENTS.md"
  "scripts/agent_worktree_start.sh"
  "scripts/agent_worktree_finish.sh"
  "scripts/bootstrap_venv.sh"
  "scripts/run_backend_pytest.sh"
)

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

for f in "scripts/agent_worktree_start.sh" "scripts/agent_worktree_finish.sh" "scripts/bootstrap_venv.sh" "scripts/run_backend_pytest.sh"; do
  if [[ ! -x "$f" ]]; then
    echo "Script is not executable: $f"
    missing=1
  fi
done

if [[ $missing -ne 0 ]]; then
  exit 1
fi

echo "Repo structure validated."
