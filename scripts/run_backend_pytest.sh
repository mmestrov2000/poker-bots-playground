#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
venv_activate="$repo_root/backend/.venv/bin/activate"

if [[ ! -f "$venv_activate" ]]; then
  echo "Missing venv at $repo_root/backend/.venv" >&2
  echo "Run scripts/bootstrap_venv.sh first." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$venv_activate"

cd "$repo_root"
PYTHONPATH=backend pytest backend/tests "$@"
